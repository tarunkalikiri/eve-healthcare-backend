import sys
from getpass import getpass
from pathlib import Path

# Add the project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.models import User


def create_admin() -> None:
    print("=== EVE Healthcare Admin Setup ===")

    email = input("Admin email: ").strip().lower()
    full_name = input("Admin full name: ").strip()
    password = getpass("Admin password: ")

    if not email or not full_name or not password:
        print("Email, name, and password are required.")
        return

    if len(password.encode("utf-8")) > 72:
        print("Password cannot exceed 72 bytes.")
        return

    db = SessionLocal()

    try:
        existing_user = db.scalar(
            select(User).where(User.email == email)
        )

        if existing_user:
            existing_user.role = "ADMIN"
            existing_user.hashed_password = hash_password(password)
            existing_user.full_name = full_name
            existing_user.is_active = True

            db.commit()

            print(f"Existing user '{email}' promoted to ADMIN.")
            return

        admin = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role="ADMIN",
            is_active=True,
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("Admin created successfully.")
        print(f"Admin ID: {admin.id}")
        print(f"Admin email: {admin.email}")

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()