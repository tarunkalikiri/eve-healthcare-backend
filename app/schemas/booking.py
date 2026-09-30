from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.models import BookingStatus


class BookingCreate(BaseModel):
    diagnostic_test_id: int = Field(gt=0)
    diagnostic_centre_id: int = Field(gt=0)
    appointment_datetime: datetime
    amount: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
    )

    @field_validator("appointment_datetime")
    @classmethod
    def normalize_appointment_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    diagnostic_test_id: int
    diagnostic_centre_id: int
    appointment_datetime: datetime
    amount: Decimal
    status: BookingStatus
    created_at: datetime
    updated_at: datetime