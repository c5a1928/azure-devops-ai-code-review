from __future__ import annotations

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_auth
from app.celery_app import celery_app
from app.git_connections_store import count_git_connections
from app.git_projects_store import count_git_projects, get_git_project
from app.review_jobs_store import create_review_job
from app.schemas import ReviewRequest, ReviewResponse, TaskStatusResponse
from app.settings_store import get_runtime_settings
from app.tasks import review_pull_request

router = APIRouter(prefix="/api")


def _review_missing_fields() -> list[str]:
    settings = get_runtime_settings()
    missing = list(settings.missing_fields())
    if count_git_connections() == 0:
        missing.append("git_connections")
    if count_git_projects() == 0:
        missing.append("git_projects")
    return missing


@router.post("/review", response_model=ReviewResponse, status_code=202)
def trigger_review(
    request: ReviewRequest,
    _: None = Depends(require_auth),
) -> ReviewResponse:
    missing = _review_missing_fields()
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Configure required settings before starting a review.",
                "missing_fields": missing,
            },
        )

    git_project = get_git_project(request.git_project_id)
    if git_project is None:
        raise HTTPException(status_code=404, detail="Git project not found.")

    project = git_project.project.strip() or None

    task = review_pull_request.delay(
        git_connection_id=git_project.git_connection_id,
        repo_name=git_project.repo,
        pr_id=request.pr_id,
        project=project,
    )
    create_review_job(
        task_id=task.id,
        git_project_id=git_project.id,
        display_path=git_project.display_path,
        platform=git_project.platform,
        repo_name=git_project.repo,
        pr_id=request.pr_id,
    )
    pr_label = "MR" if git_project.platform == "gitlab" else "PR"
    target = git_project.label or git_project.display_path
    return ReviewResponse(
        task_id=task.id,
        status="queued",
        message=f"Review queued for {target} {pr_label} #{request.pr_id}",
    )


@router.get("/review/{task_id}", response_model=TaskStatusResponse)
def get_review_status(
    task_id: str,
    _: None = Depends(require_auth),
) -> TaskStatusResponse:
    result = AsyncResult(task_id, app=celery_app)

    if result.state == "PENDING":
        return TaskStatusResponse(task_id=task_id, status="pending")
    if result.state == "PROGRESS":
        return TaskStatusResponse(
            task_id=task_id,
            status="in_progress",
            result=result.info if isinstance(result.info, dict) else None,
        )
    if result.state == "SUCCESS":
        return TaskStatusResponse(task_id=task_id, status="completed", result=result.result)
    if result.state == "FAILURE":
        return TaskStatusResponse(
            task_id=task_id,
            status="failed",
            error=str(result.info),
        )

    raise HTTPException(status_code=500, detail=f"Unknown task state: {result.state}")
