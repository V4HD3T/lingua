"""Load-test scenarios (v0.1.2).

Run against a locally started backend (from backend/):

    uvicorn app.main:app --port 8000                       # terminal 1
    locust -f loadtest/locustfile.py --host http://127.0.0.1:8000 \
           --headless -u 15 -r 5 -t 30s                    # terminal 2

Two intended modes, because per-IP rate limiting and single-IP load
generation are fundamentally at odds:

1. **Defaults** -- exercises the real system. Expect a wall of 429s: the
   whole point of the run is verifying the limiter engages under
   pressure and stays engaged. Latency numbers from this mode are
   meaningless.
2. **Capacity mode** -- start the backend with the budgets raised
   (the knobs exist for exactly this):

       API_RATE_LIMIT_PER_MINUTE=1000000 \
       TRANSLATE_RATE_LIMIT_PER_MINUTE=1000000 \
       uvicorn app.main:app --port 8000

   and rerun locust for real latency/throughput figures.

All simulated users share ONE account (created once at test start):
per-user registration would trip the auth limiters (3-5/min/IP) in the
first seconds of every run, and shared history writes are fine for load
purposes.
"""

import uuid

from locust import HttpUser, between, events, task

STATE = {"token": None}


@events.test_start.add_listener
def _create_shared_account(environment, **kwargs):
    import requests

    base = environment.host.rstrip("/")
    username = f"load_{uuid.uuid4().hex[:10]}"
    password = "password1234"
    requests.post(
        f"{base}/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
        timeout=10,
    )
    response = requests.post(
        f"{base}/auth/login", data={"username": username, "password": password}, timeout=10
    )
    if response.status_code == 200:
        STATE["token"] = response.json()["access_token"]
        print(f"[loadtest] shared account ready: {username}")
    else:
        print(f"[loadtest] WARNING: login failed ({response.status_code}); running anonymous")


class LearnerUser(HttpUser):
    wait_time = between(0.5, 2)

    @property
    def auth_headers(self):
        token = STATE["token"]
        return {"Authorization": f"Bearer {token}"} if token else {}

    @task(5)
    def translate(self):
        self.client.post(
            "/translate",
            json={"text": "hello world", "source_lang": "en", "target_lang": "es"},
            headers=self.auth_headers,
            name="/translate",
        )

    @task(2)
    def history(self):
        self.client.get("/translate/history", headers=self.auth_headers, name="/translate/history")

    @task(1)
    def courses(self):
        self.client.get("/courses", name="/courses")

    @task(1)
    def quiz(self):
        self.client.get("/lessons/1/quiz", headers=self.auth_headers, name="/lessons/1/quiz")
