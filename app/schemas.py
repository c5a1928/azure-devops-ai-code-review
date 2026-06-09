from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    repo_name: str = Field(..., description="Azure DevOps repository name, e.g. analog-ms")
    pr_id: int = Field(..., ge=1, description="Pull request ID, e.g. 1964")
    project: str | None = Field(
        default=None,
        description="Azure DevOps project name. Defaults to AZURE_DEVOPS_PROJECT from .env",
    )


class ReviewResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | None = None
    error: str | None = None
