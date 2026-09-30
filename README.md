# EVE Healthcare Backend

## 1. Project Overview

EVE Healthcare Backend is a REST API for user authentication, diagnostic-centre and test management, appointment bookings, simulated payments, and payment-provider webhooks.

## 2. Tech Stack

- Python, FastAPI, and Pydantic
- SQLAlchemy ORM and Alembic migrations
- SQLite for local development
- JWT authentication, bcrypt password hashing
- pytest and FastAPI TestClient

SQLite is used for local development because PostgreSQL was preferred but not mandatory. SQLAlchemy keeps the persistence layer portable to PostgreSQL; `psycopg2-binary` is included as its driver.

## 3. Architecture

```text
app/
  core/          settings, JWT security, authorization dependencies
  db/            SQLAlchemy engine, session, and declarative base
  models/        users, centres, tests, bookings, payments, webhook events
  routers/       auth, centres, tests, bookings, payments
  schemas/       request and response validation
  main.py        FastAPI application and router registration
alembic/         database migration environment and revisions
scripts/         interactive admin creation utility
tests/           isolated API integration tests
```

## 4. Prerequisites

Python 3.10 or newer is recommended. Run commands from the project root.

## 5. Virtual Environment

Windows PowerShell:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

macOS/Linux:

```sh
python3 -m venv venv
source venv/bin/activate
```

## 6. Install Dependencies

```sh
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 7. Environment Configuration

Copy `.env.example` to `.env`, then replace `SECRET_KEY` with a long, randomly generated value. Keep `.env` private and out of version control.

```dotenv
DATABASE_URL=sqlite:///./eve_healthcare.db
SECRET_KEY=replace-with-a-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

For PostgreSQL, set `DATABASE_URL` to a SQLAlchemy PostgreSQL URL, for example `postgresql+psycopg2://user:password@localhost/eve_healthcare`.

## 8. Database Migrations

Apply all migrations:

```sh
alembic upgrade head
```

Create a migration after changing SQLAlchemy models:

```sh
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## 9. Run the API

```sh
uvicorn app.main:app --reload
```

The local API is available at `http://127.0.0.1:8000`.

## 10. Swagger

Interactive API documentation: `http://127.0.0.1:8000/docs`. OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`.

## 11. Authentication Flow

1. Create an account using `POST /auth/signup`.
2. Exchange the email and password using `POST /auth/login`.
3. Send the returned token as `Authorization: Bearer <access_token>` to protected endpoints.
4. Inspect the authenticated account using `GET /auth/me`.

The public signup endpoint always creates a `USER`. Create or promote an administrator with `python scripts/create_admin.py` after applying database migrations.

### Signup

`POST /auth/signup`

Request:

```json
{
  "email": "alex@example.invalid",
  "full_name": "Alex Example",
  "password": "example-password-123"
}
```

Successful response (`201 Created`):

```json
{
  "id": 1,
  "email": "alex@example.invalid",
  "full_name": "Alex Example",
  "is_active": true
}
```

### Login

`POST /auth/login`

Request:

```json
{
  "email": "alex@example.invalid",
  "password": "example-password-123"
}
```

Successful response (`200 OK`):

```json
{
  "access_token": "<JWT returned by the API>",
  "token_type": "bearer"
}
```

Send the token in subsequent protected requests as `Authorization: Bearer <access_token>`.

### Current User

`GET /auth/me`

Request header:

```http
Authorization: Bearer <access_token from login>
```

Successful response (`200 OK`):

```json
{
  "id": 1,
  "email": "alex@example.invalid",
  "full_name": "Alex Example",
  "is_active": true
}
```

## 12. Important API Endpoints

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/signup` | Public | Register a user |
| POST | `/auth/login` | Public | Issue a JWT |
| GET | `/auth/me` | User | Return the current user |
| GET/POST | `/centres` | Public read / Admin write | List or create centres |
| GET/PATCH/DELETE | `/centres/{centre_id}` | Public read / Admin write | Retrieve, update, or delete a centre |
| GET/POST | `/centres/{centre_id}/tests` | Public read / Admin write | List or create centre tests |
| GET/PATCH/DELETE | `/centres/{centre_id}/tests/{test_id}` | Public read / Admin write | Retrieve, update, or delete a test |
| POST | `/bookings` | User | Create a booking |
| GET | `/bookings` | User | List the current user's bookings |
| GET | `/bookings/{booking_id}` | Owner | Retrieve a booking |
| PATCH | `/bookings/{booking_id}/cancel` | Owner | Cancel a PENDING booking |
| POST | `/payments` | User | Record one simulated payment for a booking |
| POST | `/payments/webhook` | Provider callback | Process an idempotent simulated payment event |

### Booking example

```json
{
  "diagnostic_test_id": 1,
  "diagnostic_centre_id": 1,
  "appointment_datetime": "2030-06-15T10:30:00Z",
  "amount": "125.50"
}
```

### Payment example

`status` deterministically simulates the payment provider's outcome:

```json
{
  "booking_id": 1,
  "amount": "125.50",
  "status": "SUCCESS"
}
```

The response includes the payment ID, booking ID, unique UUID transaction ID, amount, status, and timestamps.

### Webhook example

```json
{
  "event_id": "evt-unique-001",
  "transaction_id": "the-transaction-id-returned-by-payment",
  "status": "SUCCESS",
  "event_type": "payment.succeeded"
}
```

No real money or payment gateway is used; payment processing is simulated. A real payment-provider integration must verify a provider signature or shared secret before accepting webhooks. The assignment endpoint intentionally has no such signature check.

## 13. Database Schema

- `users`: email, password hash, role, and active status.
- `diagnostic_centres`: centre name and location.
- `diagnostic_tests`: centre-owned test name, description, and positive decimal price.
- `bookings`: user, centre, test, appointment, price snapshot, and status.
- `payments`: one payment per booking, unique transaction ID, amount, and outcome.
- `webhook_events`: unique processed event ID linked to a payment.

Foreign keys are enabled for SQLite connections. Centre/test deletion is rejected with `409 Conflict` when a booking references the record.

## 14. Booking and Payment State Flow

```text
PENDING --SUCCESS--> CONFIRMED
PENDING --FAILED---> FAILED
PENDING --cancel---> CANCELLED
```

Payments can only be initiated for PENDING bookings, and a booking can have only one payment attempt, including a failed attempt. Payment creation writes the payment and booking transition in one database transaction. Settled or cancelled states cannot be changed to contradictory states by a webhook.

## 15. Webhook Idempotency

`event_id` is unique in the database. A repeated event ID returns a successful response with `duplicate: true` and does not add an event or reapply the state transition. A unique-constraint conflict is handled as a replay when the committed event is found. New events must reference an existing transaction and match its recorded payment outcome.

## 16. Authorization

- Signup creates only `USER` accounts; administrator creation is an explicit script operation.
- Only active authenticated users can use protected endpoints.
- Centre and diagnostic-test changes require the `ADMIN` role.
- Users can access, cancel, or pay only for their own bookings.
- Webhooks do not use a user JWT because they represent an external provider callback.

## 17. Validation and Error Cases

Malformed payloads and unsupported enum values return `422`. Missing records return `404`; invalid centre/test relationships and incorrect amounts return `400`; duplicate payments return `409`; cross-user booking access returns `403`; invalid or expired JWTs return `401`; inactive users and non-admin management attempts return `403`. Webhook transaction lookup returns `404`, and event replay is a successful idempotent response.

## 18. Tests

Tests use a fresh in-memory SQLite database and never use the local application database:

```sh
pytest -q
```

The suite covers authentication, authorization, centre/test management, booking validation and ownership, payment outcomes and duplicates, webhook validation/idempotency, and booking/payment state updates.

## 19. Assumptions

- API datetimes without an offset are treated as UTC; offset-aware datetimes are normalized to UTC before storage.
- Booking amount must match the diagnostic-test price when the booking is created.
- A failed payment is final for that booking; retrying requires a new booking.
- A webhook status must match the stored simulated payment outcome. Contradictory transitions are rejected.
- SQLite is the default local database, not a production recommendation.

## 20. Future Improvements

- Integrate a real payment provider and verify signed webhooks.
- Add PostgreSQL-backed integration tests and deployment configuration.
- Add structured logging, request correlation IDs, and rate limiting.
- Add pagination and operational monitoring for larger datasets.

## 21. Security Notes

Passwords are stored as bcrypt hashes, never returned by API responses. Keep real `.env` values out of source control, rotate any exposed keys, and use a provider's official signature verification in production.