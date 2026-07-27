"""Delete rows that can no longer affect anything.

    python scripts/purge.py

Spent verification/reset links, refresh tokens long past expiry, and
stale quiz sessions -- see app/services/maintenance.py for each retention
window and why it sits where it does.

The app also runs this at startup unless PURGE_ON_STARTUP is off. This
script exists for the deployment that turns that off because the delete
would delay boot, and wants it on a schedule instead (a cron entry, a
platform scheduled job). Safe to run against a live database and safe to
run twice: it only ever removes rows the code already refuses to act on.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session  # noqa: E402

from app.database import engine  # noqa: E402
from app.services.maintenance import purge_expired  # noqa: E402


def main() -> None:
    with Session(engine) as session:
        removed = purge_expired(session)

    total = sum(removed.values())
    if not total:
        print("Nothing to purge.")
        return

    print(f"Removed {total} row(s):")
    for table, count in removed.items():
        if count:
            print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
