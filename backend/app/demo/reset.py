from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal
from app.demo.report import build_report
from app.demo.service import reset_demo_world


def main() -> None:
    settings = get_settings()
    clock = DemoClock.from_settings(settings)
    with SessionLocal.begin() as session:
        reset_demo_world(session, clock, settings=settings)
        report = build_report(session, clock)
    print(report)


if __name__ == "__main__":
    main()
