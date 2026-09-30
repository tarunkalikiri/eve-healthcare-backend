from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.models import (
    Booking,
    BookingStatus,
    Payment,
    PaymentStatus,
    User,
    WebhookEvent,
)
from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
    WebhookCreate,
    WebhookResponse,
)


router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        booking = db.scalar(
            select(Booking)
            .where(Booking.id == payment_data.booking_id)
            .with_for_update()
        )
        if booking is None:
            raise HTTPException(status_code=404, detail="Booking not found")
        if booking.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not authorized to pay for this booking")
        if db.scalar(select(Payment.id).where(Payment.booking_id == booking.id)):
            raise HTTPException(status_code=409, detail="A payment already exists for this booking")
        if booking.status != BookingStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Booking cannot be paid from {booking.status.value} state",
            )
        if payment_data.amount != booking.amount:
            raise HTTPException(status_code=400, detail="Payment amount does not match booking amount")

        payment = Payment(
            booking_id=booking.id,
            transaction_id=str(uuid4()),
            amount=booking.amount,
            status=payment_data.status,
        )
        booking.status = (
            BookingStatus.CONFIRMED
            if payment.status == PaymentStatus.SUCCESS
            else BookingStatus.FAILED
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A payment already exists for this booking")
    return payment


@router.post("/webhook", response_model=WebhookResponse)
def process_payment_webhook(
    webhook: WebhookCreate,
    db: Session = Depends(get_db),
):
    try:
        with db.begin():
            event = db.scalar(select(WebhookEvent).where(WebhookEvent.event_id == webhook.event_id))
            if event is not None:
                payment = db.get(Payment, event.payment_id)
                booking = db.get(Booking, payment.booking_id)
                response = WebhookResponse(
                    event_id=event.event_id,
                    transaction_id=payment.transaction_id,
                    status=payment.status,
                    booking_status=booking.status,
                    duplicate=True,
                )
            else:
                payment = db.scalar(
                    select(Payment).where(Payment.transaction_id == webhook.transaction_id)
                )
                if payment is None:
                    raise HTTPException(status_code=404, detail="Payment transaction not found")
                booking = db.get(Booking, payment.booking_id)
                expected_booking_status = (
                    BookingStatus.CONFIRMED
                    if webhook.status == PaymentStatus.SUCCESS
                    else BookingStatus.FAILED
                )
                if payment.status != webhook.status:
                    raise HTTPException(status_code=400, detail="Invalid payment state transition")
                if booking.status not in (BookingStatus.PENDING, expected_booking_status):
                    raise HTTPException(status_code=400, detail="Invalid booking state transition")

                booking.status = expected_booking_status
                db.add(
                    WebhookEvent(
                        event_id=webhook.event_id,
                        payment_id=payment.id,
                        event_type=webhook.event_type,
                    )
                )
                db.flush()
                response = WebhookResponse(
                    event_id=webhook.event_id,
                    transaction_id=payment.transaction_id,
                    status=payment.status,
                    booking_status=booking.status,
                    duplicate=False,
                )
    except IntegrityError:
        db.rollback()
        event = db.scalar(select(WebhookEvent).where(WebhookEvent.event_id == webhook.event_id))
        if event is None:
            raise HTTPException(status_code=409, detail="Webhook event conflicts with existing data")
        payment = db.get(Payment, event.payment_id)
        booking = db.get(Booking, payment.booking_id)
        response = WebhookResponse(
            event_id=event.event_id,
            transaction_id=payment.transaction_id,
            status=payment.status,
            booking_status=booking.status,
            duplicate=True,
        )
    return response