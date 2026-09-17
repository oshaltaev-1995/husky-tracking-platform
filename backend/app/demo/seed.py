from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal
from app.demo.report import build_report
from app.demo.service import assert_reset_is_safe, seed_demo_world


def main() -> None:
    settings = get_settings()
    assert_reset_is_safe(settings)
    clock = DemoClock.from_settings(settings)
    with SessionLocal.begin() as session:
        seed_demo_world(session, clock)
        report = build_report(session, clock)
    print(report)


if __name__ == "__main__":
    main()
