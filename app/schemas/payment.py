from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.models import BookingStatus, PaymentStatus


class PaymentCreate(BaseModel):
    booking_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    status: PaymentStatus


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    transaction_id: str
    amount: Decimal
    status: PaymentStatus
    created_at: datetime
    updated_at: datetime


class WebhookCreate(BaseModel):
    event_id: str = Field(min_length=1, max_length=150)
    transaction_id: str = Field(min_length=1, max_length=100)
    status: PaymentStatus
    event_type: Literal["payment.succeeded", "payment.failed"]

    @model_validator(mode="after")
    def status_matches_event_type(self):
        expected_status = {
            "payment.succeeded": PaymentStatus.SUCCESS,
            "payment.failed": PaymentStatus.FAILED,
        }[self.event_type]
        if self.status != expected_status:
            raise ValueError("event_type must match status")
        return self


class WebhookResponse(BaseModel):
    event_id: str
    transaction_id: str
    status: PaymentStatus
    booking_status: BookingStatus
    duplicate: bool