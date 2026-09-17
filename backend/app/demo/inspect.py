from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import SessionLocal
from app.demo.report import build_report


def main() -> None:
    clock = DemoClock.from_settings(get_settings())
    with SessionLocal() as session:
        print(build_report(session, clock))


if __name__ == "__main__":
    main()
