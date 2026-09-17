from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.demo_clock import DemoClock
from app.db.session import get_db
from app.models import DemoDataset, DogLifecyclePeriod
from app.models.enums import LifecycleState

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]


class DemoDatasetSummary(BaseModel):
    dataset_version: str
    reference_date: date
    active_dogs: int
    archived_dogs: int
    semantic_checksum: str


@router.get("/demo-dataset", response_model=DemoDatasetSummary)
def demo_dataset_summary(session: DatabaseSession) -> DemoDatasetSummary:
    clock = DemoClock.from_settings(get_settings())
    dataset = session.scalar(select(DemoDataset))
    if not dataset or not dataset.semantic_checksum:
        raise HTTPException(
            status_code=404, detail="canonical demo dataset is not seeded"
        )

    def lifecycle_count(state: LifecycleState) -> int:
        return (
            session.scalar(
                select(func.count())
                .select_from(DogLifecyclePeriod)
                .where(
                    DogLifecyclePeriod.lifecycle_state == state.value,
                    DogLifecyclePeriod.valid_from <= clock.reference_date,
                    (DogLifecyclePeriod.valid_to.is_(None))
                    | (DogLifecyclePeriod.valid_to > clock.reference_date),
                )
            )
            or 0
        )

    return DemoDatasetSummary(
        dataset_version=dataset.version,
        reference_date=clock.reference_date,
        active_dogs=lifecycle_count(LifecycleState.ACTIVE),
        archived_dogs=lifecycle_count(LifecycleState.ARCHIVED),
        semantic_checksum=dataset.semantic_checksum,
    )
