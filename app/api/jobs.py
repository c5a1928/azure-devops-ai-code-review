from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_auth
from app.review_jobs_store import get_review_job, list_review_jobs
from app.schemas import ReviewJobPublic

router = APIRouter(prefix="/api")


@router.get("/jobs", response_model=list[ReviewJobPublic])
def read_jobs(_: None = Depends(require_auth)) -> list[ReviewJobPublic]:
    return list_review_jobs()


@router.get("/jobs/{task_id}", response_model=ReviewJobPublic)
def read_job(task_id: str, _: None = Depends(require_auth)) -> ReviewJobPublic:
    job = get_review_job(task_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job
