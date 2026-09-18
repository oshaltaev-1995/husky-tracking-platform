"""Initialize a fresh database with the immutable synthetic baseline.

Unlike the development reset command, this operation never truncates existing data.
It is intended as an explicit, one-time deployment step after Alembic migrations.
"""

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal
from app.demo.catalog import EXPECTED_SEMANTIC_CHECKSUM
from app.demo.service import DemoAlreadySeededError, seed_demo_world


def main() -> None:
    settings = get_settings()
    clock = DemoClock.from_settings(settings)
    try:
        with SessionLocal.begin() as session:
            checksum = seed_demo_world(session, clock, require_empty=True)
            if checksum != EXPECTED_SEMANTIC_CHECKSUM:
                raise RuntimeError("canonical demo checksum did not match the release")
    except DemoAlreadySeededError:
        raise SystemExit(
            "Initialization refused: canonical domain data already exists."
        ) from None
    print(f"Initialized canonical demo baseline: {checksum}")


if __name__ == "__main__":
    main()
