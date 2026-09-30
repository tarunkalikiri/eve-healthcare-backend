from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.db.database import get_db
from app.models.models import DiagnosticCentre, User
from app.schemas.centre import (
    DiagnosticCentreCreate,
    DiagnosticCentreResponse,
    DiagnosticCentreUpdate,
)


router = APIRouter(prefix="/centres", tags=["Diagnostic Centres"])


@router.post("", response_model=DiagnosticCentreResponse, status_code=status.HTTP_201_CREATED)
def create_centre(
    centre_data: DiagnosticCentreCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    centre = DiagnosticCentre(**centre_data.model_dump())
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


@router.get("", response_model=list[DiagnosticCentreResponse])
def list_centres(db: Session = Depends(get_db)):
    return db.scalars(select(DiagnosticCentre).order_by(DiagnosticCentre.id)).all()


@router.get("/{centre_id}", response_model=DiagnosticCentreResponse)
def get_centre(centre_id: int, db: Session = Depends(get_db)):
    centre = db.get(DiagnosticCentre, centre_id)
    if centre is None:
        raise HTTPException(status_code=404, detail="Diagnostic centre not found")
    return centre


@router.patch("/{centre_id}", response_model=DiagnosticCentreResponse)
def update_centre(
    centre_id: int,
    update: DiagnosticCentreUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    centre = db.get(DiagnosticCentre, centre_id)
    if centre is None:
        raise HTTPException(status_code=404, detail="Diagnostic centre not found")
    values = update.model_dump(exclude_unset=True)
    if not values or any(value is None for value in values.values()):
        raise HTTPException(status_code=422, detail="Provide at least one non-null field")
    for field, value in values.items():
        setattr(centre, field, value)
    db.commit()
    db.refresh(centre)
    return centre


@router.delete("/{centre_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_centre(
    centre_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    centre = db.get(DiagnosticCentre, centre_id)
    if centre is None:
        raise HTTPException(status_code=404, detail="Diagnostic centre not found")
    db.delete(centre)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Centre has existing bookings")