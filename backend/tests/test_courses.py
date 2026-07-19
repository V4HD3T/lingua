def test_list_courses(client):
    response = client.get("/courses")
    assert response.status_code == 200
    courses = response.json()
    assert len(courses) == 1
    assert courses[0]["title"] == "Spanish for Beginners"


def test_get_course(client):
    response = client.get("/courses/1")
    assert response.status_code == 200
    assert response.json()["language_code"] == "es"


def test_get_missing_course_returns_404(client):
    response = client.get("/courses/999")
    assert response.status_code == 404


def test_list_lessons_includes_language_code(client):
    response = client.get("/courses/1/lessons")
    assert response.status_code == 200
    lessons = response.json()
    assert len(lessons) == 1
    assert lessons[0]["language_code"] == "es"
    assert lessons[0]["course_id"] == 1


def test_get_lesson(client):
    response = client.get("/lessons/1")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Greetings"
    assert data["language_code"] == "es"
    assert "cheek kiss" in data["cultural_note"]
    assert "tú" in data["grammar_note"]


def test_get_missing_lesson_returns_404(client):
    response = client.get("/lessons/999")
    assert response.status_code == 404


def test_list_vocabulary(client):
    response = client.get("/lessons/1/vocabulary")
    assert response.status_code == 200
    words = {item["word"] for item in response.json()}
    assert {"hola", "adiós"}.issubset(words)
