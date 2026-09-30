from pydantic import BaseModel, ConfigDict, Field


class DiagnosticCentreCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    location: str = Field(min_length=2, max_length=300)


class DiagnosticCentreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    location: str | None = Field(default=None, min_length=2, max_length=300)


class DiagnosticCentreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str