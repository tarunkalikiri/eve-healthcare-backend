from datetime import datetime, timedelta, timezone
from decimal import Decimal

from jose import jwt
from sqlalchemy import func, select

from app.core.config import settings
from app.models.models import (
    Booking,
    BookingStatus,
    Payment,
    PaymentStatus,
    User,
    WebhookEvent,
)
from tests.conftest import create_booking, create_centre, create_test


def test_auth_signup_login_and_protected_endpoint(api):
    client = api["client"]
    signup = client.post(
        "/auth/signup",
        json={"email": "new@example.com", "full_name": "New User", "password": "new-password"},
    )
    assert signup.status_code == 201
    assert "hashed_password" not in signup.json()
    assert client.post(
        "/auth/signup",
        json={"email": "new@example.com", "full_name": "New User", "password": "new-password"},
    ).status_code == 409

    login = client.post(
        "/auth/login",
        json={"email": "new@example.com", "password": "new-password"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "new@example.com"
    assert client.post(
        "/auth/login",
        json={"email": "new@example.com", "password": "incorrect"},
    ).status_code == 401


def test_signup_password_utf8_byte_limits(api):
    client = api["client"]
    valid_passwords = {
        "normal@example.com": "normal-password-123",
        "ascii72@example.com": "a" * 72,
        "unicode72@example.com": "€" * 24,
    }
    for email, password in valid_passwords.items():
        response = client.post(
            "/auth/signup",
            json={"email": email, "full_name": "Valid Password", "password": password},
        )
        assert response.status_code == 201

    invalid_passwords = {
        "short@example.com": "short",
        "ascii73@example.com": "a" * 73,
        "unicode75@example.com": "€" * 25,
    }
    for email, password in invalid_passwords.items():
        response = client.post(
            "/auth/signup",
            json={"email": email, "full_name": "Invalid Password", "password": password},
        )
        assert response.status_code == 422


def test_expired_jwt_and_inactive_user_are_rejected(api):
    client = api["client"]
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    with api["session"]() as db:
        user = db.scalar(select(User).where(User.email == "user@example.com"))
        user.is_active = False
        db.commit()
    assert client.get("/auth/me", headers=api["headers"]["user"]).status_code == 403


def test_centres_admin_access_and_retrieval(api):
    client = api["client"]
    assert client.post(
        "/centres",
        json={"name": "Blocked Clinic", "location": "Elsewhere"},
        headers=api["headers"]["user"],
    ).status_code == 403
    centre = create_centre(api)
    assert client.get("/centres").json()[0]["id"] == centre["id"]
    assert client.get(f"/centres/{centre['id']}").status_code == 200
    assert client.get("/centres/99999").status_code == 404
    assert client.patch(
        f"/centres/{centre['id']}",
        json={"name": "Updated Clinic"},
        headers=api["headers"]["user"],
    ).status_code == 403


def test_diagnostic_tests_admin_access_and_centre_relationship(api):
    client = api["client"]
    centre = create_centre(api)
    other_centre = create_centre(api, "South Clinic")
    test = create_test(api, centre["id"])
    assert client.post(
        f"/centres/{centre['id']}/tests",
        json={"name": "Unauthorized Test", "price": "10.00"},
        headers=api["headers"]["user"],
    ).status_code == 403
    assert client.get(f"/centres/{centre['id']}/tests").json()[0]["id"] == test["id"]
    assert client.get(f"/centres/{centre['id']}/tests/{test['id']}").status_code == 200
    assert client.get(f"/centres/{other_centre['id']}/tests/{test['id']}").status_code == 404
    assert client.post(
        "/centres/99999/tests",
        json={"name": "Orphan Test", "price": "10.00"},
        headers=api["headers"]["admin"],
    ).status_code == 404
    assert client.post(
        f"/centres/{centre['id']}/tests",
        json={"name": "Free Test", "price": "0"},
        headers=api["headers"]["admin"],
    ).status_code == 422


def test_booking_validation_ownership_and_cancellation(api):
    client = api["client"]
    centre = create_centre(api)
    other_centre = create_centre(api, "West Clinic")
    test = create_test(api, centre["id"])
    future = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    payload = {
        "diagnostic_centre_id": centre["id"],
        "diagnostic_test_id": test["id"],
        "appointment_datetime": future,
        "amount": "125.50",
    }
    created = client.post("/bookings", json=payload, headers=api["headers"]["user"])
    assert created.status_code == 201
    booking_id = created.json()["id"]
    assert client.get(f"/bookings/{booking_id}", headers=api["headers"]["second"]).status_code == 403
    assert client.patch(
        f"/bookings/{booking_id}/cancel",
        headers=api["headers"]["second"],
    ).status_code == 403
    assert client.patch(
        f"/bookings/{booking_id}/cancel",
        headers=api["headers"]["user"],
    ).json()["status"] == "CANCELLED"

    invalid = dict(payload, diagnostic_centre_id=99999)
    assert client.post("/bookings", json=invalid, headers=api["headers"]["user"]).status_code == 404
    invalid = dict(payload, diagnostic_test_id=99999)
    assert client.post("/bookings", json=invalid, headers=api["headers"]["user"]).status_code == 404
    invalid = dict(payload, diagnostic_centre_id=other_centre["id"])
    assert client.post("/bookings", json=invalid, headers=api["headers"]["user"]).status_code == 400
    invalid = dict(
        payload,
        appointment_datetime=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    )
    assert client.post("/bookings", json=invalid, headers=api["headers"]["user"]).status_code == 400
    invalid = dict(payload, amount="125.49")
    assert client.post("/bookings", json=invalid, headers=api["headers"]["user"]).status_code == 400
    assert client.post(
        "/bookings",
        json=dict(payload, appointment_datetime="not-a-datetime"),
        headers=api["headers"]["user"],
    ).status_code == 422


def test_payment_success_failure_duplicate_amount_and_ownership(api):
    client = api["client"]
    booking = create_booking(api)
    response = client.post(
        "/payments",
        json={"booking_id": booking["id"], "amount": "125.50", "status": "SUCCESS"},
        headers=api["headers"]["user"],
    )
    assert response.status_code == 201
    payment = response.json()
    assert payment["status"] == "SUCCESS"
    assert payment["transaction_id"]
    assert client.get(f"/bookings/{booking['id']}", headers=api["headers"]["user"]).json()["status"] == "CONFIRMED"
    assert client.post(
        "/payments",
        json={"booking_id": booking["id"], "amount": "125.50", "status": "SUCCESS"},
        headers=api["headers"]["user"],
    ).status_code == 409

    failed_booking = create_booking(api)
    failed = client.post(
        "/payments",
        json={"booking_id": failed_booking["id"], "amount": "125.50", "status": "FAILED"},
        headers=api["headers"]["user"],
    )
    assert failed.status_code == 201
    assert client.get(f"/bookings/{failed_booking['id']}", headers=api["headers"]["user"]).json()["status"] == "FAILED"

    wrong_amount_booking = create_booking(api)
    assert client.post(
        "/payments",
        json={"booking_id": wrong_amount_booking["id"], "amount": "1.00", "status": "SUCCESS"},
        headers=api["headers"]["user"],
    ).status_code == 400
    assert client.post(
        "/payments",
        json={"booking_id": wrong_amount_booking["id"], "amount": "125.50", "status": "SUCCESS"},
        headers=api["headers"]["second"],
    ).status_code == 403
    assert client.post(
        "/payments",
        json={"booking_id": 99999, "amount": "125.50", "status": "SUCCESS"},
        headers=api["headers"]["user"],
    ).status_code == 404
    assert client.post(
        "/payments",
        json={"booking_id": wrong_amount_booking["id"], "amount": "125.50", "status": "UNKNOWN"},
        headers=api["headers"]["user"],
    ).status_code == 422


def test_payment_rejected_for_cancelled_booking(api):
    client = api["client"]
    booking = create_booking(api)
    assert client.patch(
        f"/bookings/{booking['id']}/cancel",
        headers=api["headers"]["user"],
    ).status_code == 200
    response = client.post(
        "/payments",
        json={"booking_id": booking["id"], "amount": "125.50", "status": "SUCCESS"},
        headers=api["headers"]["user"],
    )
    assert response.status_code == 400


def test_successful_webhook_updates_state_and_is_idempotent(api):
    client = api["client"]
    booking = create_booking(api)
    payment = client.post(
        "/payments",
        json={"booking_id": booking["id"], "amount": "125.50", "status": "SUCCESS"},
        headers=api["headers"]["user"],
    ).json()
    event = {
        "event_id": "evt-success-1",
        "transaction_id": payment["transaction_id"],
        "status": "SUCCESS",
        "event_type": "payment.succeeded",
    }
    first = client.post("/payments/webhook", json=event)
    second = client.post("/payments/webhook", json=event)
    assert first.status_code == 200
    assert first.json()["booking_status"] == "CONFIRMED"
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    with api["session"]() as db:
        assert db.scalar(select(func.count()).select_from(WebhookEvent)) == 1


def test_successful_webhook_confirms_pending_booking(api):
    client = api["client"]
    booking = create_booking(api)
    payment = Payment(
        booking_id=booking["id"],
        transaction_id="txn-pending-webhook-success",
        amount=Decimal("125.50"),
        status=PaymentStatus.SUCCESS,
    )
    with api["session"]() as db:
        db.add(payment)
        db.commit()
        assert db.get(Booking, booking["id"]).status == BookingStatus.PENDING

    response = client.post(
        "/payments/webhook",
        json={
            "event_id": "evt-pending-webhook-success",
            "transaction_id": "txn-pending-webhook-success",
            "status": "SUCCESS",
            "event_type": "payment.succeeded",
        },
    )
    assert response.status_code == 200
    with api["session"]() as db:
        stored_booking = db.get(Booking, booking["id"])
        stored_payment = db.scalar(select(Payment).where(Payment.booking_id == booking["id"]))
        assert stored_payment.status == PaymentStatus.SUCCESS
        assert stored_booking.status == BookingStatus.CONFIRMED


def test_failed_webhook_updates_booking(api):
    client = api["client"]
    booking = create_booking(api)
    payment = client.post(
        "/payments",
        json={"booking_id": booking["id"], "amount": "125.50", "status": "FAILED"},
        headers=api["headers"]["user"],
    ).json()
    response = client.post(
        "/payments/webhook",
        json={
            "event_id": "evt-failed-1",
            "transaction_id": payment["transaction_id"],
            "status": "FAILED",
            "event_type": "payment.failed",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "FAILED"
    assert response.json()["booking_status"] == "FAILED"


def test_webhook_invalid_transaction_payload_and_state_transition(api):
    client = api["client"]
    assert client.post(
        "/payments/webhook",
        json={
            "event_id": "evt-missing",
            "transaction_id": "no-such-transaction",
            "status": "SUCCESS",
            "event_type": "payment.succeeded",
        },
    ).status_code == 404
    valid_base = {
        "event_id": "evt-invalid",
        "transaction_id": "unused",
        "status": "SUCCESS",
        "event_type": "payment.succeeded",
    }
    assert client.post("/payments/webhook", json=dict(valid_base, status="PENDING")).status_code == 422
    assert client.post("/payments/webhook", json=dict(valid_base, event_type="unknown")).status_code == 422

    booking = create_booking(api)
    payment = Payment(
        booking_id=booking["id"],
        transaction_id="txn-transition",
        amount=Decimal("125.50"),
        status=PaymentStatus.FAILED,
    )
    with api["session"]() as db:
        db.add(payment)
        db.commit()
    response = client.post(
        "/payments/webhook",
        json={
            "event_id": "evt-transition",
            "transaction_id": "txn-transition",
            "status": "SUCCESS",
            "event_type": "payment.succeeded",
        },
    )
    assert response.status_code == 400
    with api["session"]() as db:
        assert db.scalar(select(func.count()).select_from(WebhookEvent)) == 0


def test_payment_and_booking_update_atomically(api):
    client = api["client"]
    booking = create_booking(api)
    response = client.post(
        "/payments",
        json={"booking_id": booking["id"], "amount": "125.50", "status": "SUCCESS"},
        headers=api["headers"]["user"],
    )
    assert response.status_code == 201
    with api["session"]() as db:
        stored_booking = db.get(Booking, booking["id"])
        stored_payment = db.scalar(select(Payment).where(Payment.booking_id == booking["id"]))
        assert stored_booking.status == BookingStatus.CONFIRMED
        assert stored_payment.status == PaymentStatus.SUCCESS