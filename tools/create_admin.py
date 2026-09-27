import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db.users import get_user_by_nickname, create_user  # noqa: E402
from utils.password_hash import generate_password_hash  # noqa: E402


def main() -> int:
    if get_user_by_nickname("admin"):
        print("Admin user already exists, skipping.")
        return 0

    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        print("ADMIN_PASSWORD is not set in the environment.")
        return 1

    password_hash = generate_password_hash(admin_password)
    user_id = create_user("admin", password_hash)
    print(f"Created admin user (id={user_id}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
