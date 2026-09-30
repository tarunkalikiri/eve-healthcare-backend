from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.db.database import get_db
from app.models.models import DiagnosticCentre, DiagnosticTest, User
from app.schemas.test import (
    DiagnosticTestCreate,
    DiagnosticTestResponse,
    DiagnosticTestUpdate,
)


router = APIRouter(prefix="/centres", tags=["Diagnostic Tests"])


def _get_test(db: Session, centre_id: int, test_id: int) -> DiagnosticTest:
    diagnostic_test = db.scalar(
        select(DiagnosticTest).where(
            DiagnosticTest.id == test_id,
            DiagnosticTest.centre_id == centre_id,
        )
    )
    if diagnostic_test is None:
        raise HTTPException(status_code=404, detail="Diagnostic test not found for this centre")
    return diagnostic_test


@router.post(
    "/{centre_id}/tests",
    response_model=DiagnosticTestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_test(
    centre_id: int,
    test_data: DiagnosticTestCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    if db.get(DiagnosticCentre, centre_id) is None:
        raise HTTPException(status_code=404, detail="Diagnostic centre not found")
    diagnostic_test = DiagnosticTest(centre_id=centre_id, **test_data.model_dump())
    db.add(diagnostic_test)
    db.commit()
    db.refresh(diagnostic_test)
    return diagnostic_test


@router.get("/{centre_id}/tests", response_model=list[DiagnosticTestResponse])
def list_tests(centre_id: int, db: Session = Depends(get_db)):
    if db.get(DiagnosticCentre, centre_id) is None:
        raise HTTPException(status_code=404, detail="Diagnostic centre not found")
    return db.scalars(
        select(DiagnosticTest)
        .where(DiagnosticTest.centre_id == centre_id)
        .order_by(DiagnosticTest.id)
    ).all()


@router.get("/{centre_id}/tests/{test_id}", response_model=DiagnosticTestResponse)
def get_test(centre_id: int, test_id: int, db: Session = Depends(get_db)):
    return _get_test(db, centre_id, test_id)


@router.patch(
    "/{centre_id}/tests/{test_id}",
    response_model=DiagnosticTestResponse,
)
def update_test(
    centre_id: int,
    test_id: int,
    update: DiagnosticTestUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    diagnostic_test = _get_test(db, centre_id, test_id)
    values = update.model_dump(exclude_unset=True)
    if not values or any(value is None for field, value in values.items() if field != "description"):
        raise HTTPException(status_code=422, detail="Provide at least one valid field")
    for field, value in values.items():
        setattr(diagnostic_test, field, value)
    db.commit()
    db.refresh(diagnostic_test)
    return diagnostic_test


@router.delete(
    "/{centre_id}/tests/{test_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_test(
    centre_id: int,
    test_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    diagnostic_test = _get_test(db, centre_id, test_id)
    db.delete(diagnostic_test)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Test has existing bookings")