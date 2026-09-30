from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.models import (
    Booking,
    BookingStatus,
    DiagnosticCentre,
    DiagnosticTest,
    User,
)
from app.schemas.booking import (
    BookingCreate,
    BookingResponse,
)


router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"],
)


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_booking(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate diagnostic centre
    centre = db.get(
        DiagnosticCentre,
        booking_data.diagnostic_centre_id,
    )

    if not centre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnostic centre not found",
        )

    # Validate diagnostic test
    diagnostic_test = db.get(
        DiagnosticTest,
        booking_data.diagnostic_test_id,
    )

    if not diagnostic_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnostic test not found",
        )

    # Make sure the test belongs to the selected centre
    if diagnostic_test.centre_id != booking_data.diagnostic_centre_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diagnostic test does not belong to the selected centre",
        )

    # Validate appointment date/time
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if booking_data.appointment_datetime <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment date and time must be in the future",
        )

    # Validate amount against the actual test price
    if booking_data.amount != diagnostic_test.price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking amount does not match the diagnostic test price",
        )

    booking = Booking(
        user_id=current_user.id,
        diagnostic_test_id=diagnostic_test.id,
        diagnostic_centre_id=centre.id,
        appointment_datetime=booking_data.appointment_datetime,
        amount=diagnostic_test.price,
        status=BookingStatus.PENDING,
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    return booking


@router.get(
    "",
    response_model=list[BookingResponse],
)
def list_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(Booking)
        .where(Booking.user_id == current_user.id)
        .order_by(Booking.created_at.desc())
    ).all()


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.get(Booking, booking_id)

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    # Users can only access their own bookings
    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this booking",
        )

    return booking


@router.patch(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.get(Booking, booking_id)

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to modify this booking",
        )

    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking cannot be cancelled from {booking.status.value} state",
        )

    booking.status = BookingStatus.CANCELLED

    db.commit()
    db.refresh(booking)

    return booking