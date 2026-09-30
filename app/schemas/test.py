from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DiagnosticTestCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class DiagnosticTestUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)


class DiagnosticTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    centre_id: int
    name: str
    description: str | None
    price: Decimal