"""Imports course content packs from backend/content/ into the database.

    python scripts/import_content.py                 # every shipped pack
    python scripts/import_content.py turkish-a1      # one pack by name
    python scripts/import_content.py --list          # show what's available

Idempotent: a course that's already present is skipped, so this is safe
to re-run after a deploy. Like scripts/make_admin.py, it works directly
against the database rather than through the admin API — no bootstrap
admin account needed just to load content.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session  # noqa: E402

from app.database import engine  # noqa: E402
from app.services.content_import import (  # noqa: E402
    CONTENT_DIR,
    available_packs,
    import_pack,
    load_pack,
)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    packs = available_packs()

    # Fail loudly rather than exiting 0 having done nothing: a missing
    # content directory (e.g. a container image that didn't ship it) used
    # to look exactly like a successful import in deployment logs.
    if not packs:
        print(
            f"No content packs found in {CONTENT_DIR}. "
            "Is the content/ directory present in this environment?",
            file=sys.stderr,
        )
        return 1

    if "--list" in sys.argv:
        print("Available content packs:")
        for path in packs:
            pack = load_pack(path)
            print(f"  {path.stem:<20} {pack.course.title} ({len(pack.lessons)} lessons)")
        return 0

    if args:
        packs = [CONTENT_DIR / f"{name.removesuffix('.json')}.json" for name in args]
        missing = [p for p in packs if not p.exists()]
        if missing:
            print(f"No such pack: {', '.join(p.stem for p in missing)}", file=sys.stderr)
            return 1

    with Session(engine) as session:
        for path in packs:
            try:
                pack = load_pack(path)
            except Exception as error:  # validation failures should be loud
                print(f"{path.name}: invalid pack -- {error}", file=sys.stderr)
                return 1
            course = import_pack(pack, session)
            if course is None:
                print(f"{path.stem}: already imported, skipping")
            else:
                print(f"{path.stem}: imported '{course.title}' ({len(pack.lessons)} lessons)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
