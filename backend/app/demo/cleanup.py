from app.db.session import SessionLocal
from app.services.demo_workspace_service import cleanup_expired_workspaces


def main() -> None:
    with SessionLocal.begin() as session:
        removed = cleanup_expired_workspaces(session)
    print(f"Removed {removed} expired demo workspace(s).")


if __name__ == "__main__":
    main()
