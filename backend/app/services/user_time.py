"""What "today" means for a given learner (v0.1.9).

Every timestamp this app stores is UTC, and that stays true -- storing
local times would be the actual mistake. What was wrong is that the app
also *asked what day it is* in UTC, and a day is not a physical quantity:
it is a thing that starts and ends where the person is.

The consequences were not subtle. In UTC+3, the day rolled over at 03:00
local, so a session at 01:00 was credited to yesterday. West of UTC it is
worse: in UTC-5 the day rolled at 19:00, so an evening review was credited
to *tomorrow*, and the review queue's "due today" was computed against a
date the learner had not reached yet. Streaks -- the whole motivational
mechanic of a language-learning app -- broke accordingly, and a learner
who studied at 01:00 and again at 23:00 the same local day could have that
counted as two separate days.

CI never saw any of it: GitHub runners are UTC, where local and UTC agree
and the bug is invisible by construction.

The fix is to convert at the point of the question, not at the point of
storage: `local_date` maps a stored UTC instant to the calendar date it
fell on for that learner, and `today_in` asks what day it currently is for
them. Both take a zone resolved from the user's own `timezone` column.

zoneinfo (stdlib) does the work, backed by the `tzdata` package rather
than the operating system's database -- Windows ships no such database at
all, so without it this module would work in the Linux container and raise
on a developer's machine.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc
DEFAULT_TIMEZONE = "UTC"
_UTC_ZONE = ZoneInfo("UTC")


def is_valid_timezone(name: str) -> bool:
    """Whether `name` is an IANA zone this system can resolve."""
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def resolve_zone(name: str | None) -> ZoneInfo:
    """The learner's zone, falling back to UTC.

    Deliberately total -- it never raises. The column is validated on the
    way in, but a row written before that validation existed, or one
    naming a zone that a later tzdata release dropped, must not turn every
    stats request into a 500. Falling back to UTC restores exactly the old
    behaviour for that user rather than breaking their account.
    """
    if not name:
        return _UTC_ZONE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return _UTC_ZONE


def local_date(moment: datetime, zone: ZoneInfo) -> date:
    """The calendar date `moment` fell on, as seen from `zone`.

    Naive values are read as UTC: SQLite hands datetimes back without
    tzinfo even though every one this app writes was created with
    datetime.now(timezone.utc). Labelling them (never shifting them) is
    correct precisely because every write path normalises to UTC first --
    the same reasoning as _as_aware_utc in app/routers/auth.py.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(zone).date()


def today_in(zone: ZoneInfo) -> date:
    """What day it is right now, where the learner is."""
    return datetime.now(UTC).astimezone(zone).date()
