from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException

from app.celery_app import celery_app
from app.schemas import ReviewRequest, ReviewResponse, TaskStatusResponse
from app.tasks import review_pull_request

app = FastAPI(
    title="Azure DevOps Code Review",
    description="Trigger automated PR reviews via Azure DevOps API",
    version="1.0.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/review", response_model=ReviewResponse, status_code=202)
def trigger_review(request: ReviewRequest) -> ReviewResponse:
    task = review_pull_request.delay(
        repo_name=request.repo_name,
        pr_id=request.pr_id,
        project=request.project,
    )
    return ReviewResponse(
        task_id=task.id,
        status="queued",
        message=f"Review queued for {request.repo_name} PR #{request.pr_id}",
    )


@app.get("/review/{task_id}", response_model=TaskStatusResponse)
def get_review_status(task_id: str) -> TaskStatusResponse:
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
