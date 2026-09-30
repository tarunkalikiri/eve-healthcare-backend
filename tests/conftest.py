from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.database import Base, get_db
from app.main import app
from app.models.models import User


@pytest.fixture
def api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    @event.listens_for(engine, "connect")
    def enable_test_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Iterator:
        with test_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with test_session() as db:
        user = User(
            email="user@example.com",
            full_name="Test User",
            hashed_password=hash_password("user-password"),
        )
        second_user = User(
            email="second@example.com",
            full_name="Second User",
            hashed_password=hash_password("user-password"),
        )
        admin = User(
            email="admin@example.com",
            full_name="Test Admin",
            hashed_password=hash_password("admin-password"),
            role="ADMIN",
        )
        db.add_all([user, second_user, admin])
        db.commit()
        headers = {
            "user": {"Authorization": f"Bearer {create_access_token(str(user.id))}"},
            "second": {"Authorization": f"Bearer {create_access_token(str(second_user.id))}"},
            "admin": {"Authorization": f"Bearer {create_access_token(str(admin.id))}"},
        }

    try:
        with TestClient(app) as client:
            yield {"client": client, "headers": headers, "session": test_session}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_centre(api, name="North Clinic"):
    response = api["client"].post(
        "/centres",
        json={"name": name, "location": "Central District"},
        headers=api["headers"]["admin"],
    )
    assert response.status_code == 201
    return response.json()


def create_test(api, centre_id, price="125.50"):
    response = api["client"].post(
        f"/centres/{centre_id}/tests",
        json={"name": "Complete Blood Count", "description": "CBC", "price": price},
        headers=api["headers"]["admin"],
    )
    assert response.status_code == 201
    return response.json()


def create_booking(api, user="user", amount="125.50", centre_id=None, test_id=None, appointment=None):
    from datetime import datetime, timedelta

    centre = create_centre(api) if centre_id is None else {"id": centre_id}
    diagnostic_test = create_test(api, centre["id"]) if test_id is None else {"id": test_id}
    payload = {
        "diagnostic_centre_id": centre["id"],
        "diagnostic_test_id": diagnostic_test["id"],
        "appointment_datetime": appointment
        or (datetime.now().astimezone() + timedelta(days=3)).isoformat(),
        "amount": amount,
    }
    response = api["client"].post(
        "/bookings",
        json=payload,
        headers=api["headers"][user],
    )
    assert response.status_code == 201
    return response.json()