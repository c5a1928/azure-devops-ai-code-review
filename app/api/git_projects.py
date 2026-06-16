from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_auth
from app.git_projects_store import (
    create_git_project,
    delete_git_project,
    list_git_projects,
    update_git_project,
)
from app.schemas import GitProjectCreate, GitProjectPublic, GitProjectUpdate

router = APIRouter(prefix="/api")


@router.get("/git-projects", response_model=list[GitProjectPublic])
def read_git_projects() -> list[GitProjectPublic]:
    return list_git_projects()


@router.post("/git-projects", response_model=GitProjectPublic, status_code=201)
def add_git_project(
    payload: GitProjectCreate,
    _: None = Depends(require_auth),
) -> GitProjectPublic:
    try:
        return create_git_project(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/git-projects/{project_id}", response_model=GitProjectPublic)
def save_git_project(
    project_id: int,
    payload: GitProjectUpdate,
    _: None = Depends(require_auth),
) -> GitProjectPublic:
    try:
        return update_git_project(project_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/git-projects/{project_id}", status_code=204)
def remove_git_project(
    project_id: int,
    _: None = Depends(require_auth),
) -> None:
    try:
        delete_git_project(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
