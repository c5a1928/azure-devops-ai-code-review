from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_auth
from app.review_jobs_store import (
    archive_review_job,
    delete_review_job,
    get_review_job,
    list_review_jobs,
    unarchive_review_job,
)
from app.schemas import ReviewJobPublic

router = APIRouter(prefix="/api")


@router.get("/jobs", response_model=list[ReviewJobPublic])
def read_jobs(
    include_archived: bool = Query(default=False),
    _: None = Depends(require_auth),
) -> list[ReviewJobPublic]:
    return list_review_jobs(include_archived=include_archived)


@router.get("/jobs/{task_id}", response_model=ReviewJobPublic)
def read_job(task_id: str, _: None = Depends(require_auth)) -> ReviewJobPublic:
    job = get_review_job(task_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.post("/jobs/{task_id}/archive", response_model=ReviewJobPublic)
def archive_job(task_id: str, _: None = Depends(require_auth)) -> ReviewJobPublic:
    try:
        return archive_review_job(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jobs/{task_id}/unarchive", response_model=ReviewJobPublic)
def unarchive_job(task_id: str, _: None = Depends(require_auth)) -> ReviewJobPublic:
    try:
        return unarchive_review_job(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/jobs/{task_id}", status_code=204)
def remove_job(task_id: str, _: None = Depends(require_auth)) -> None:
    try:
        delete_review_job(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
