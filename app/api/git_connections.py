from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_auth
from app.git_connections_store import (
    create_git_connection,
    delete_git_connection,
    list_git_connections,
    update_git_connection,
)
from app.schemas import GitConnectionCreate, GitConnectionPublic, GitConnectionUpdate

router = APIRouter(prefix="/api")


@router.get("/git-connections", response_model=list[GitConnectionPublic])
def read_git_connections() -> list[GitConnectionPublic]:
    return list_git_connections()


@router.post("/git-connections", response_model=GitConnectionPublic, status_code=201)
def add_git_connection(
    payload: GitConnectionCreate,
    _: None = Depends(require_auth),
) -> GitConnectionPublic:
    try:
        return create_git_connection(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/git-connections/{connection_id}", response_model=GitConnectionPublic)
def save_git_connection(
    connection_id: int,
    payload: GitConnectionUpdate,
    _: None = Depends(require_auth),
) -> GitConnectionPublic:
    try:
        return update_git_connection(connection_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/git-connections/{connection_id}", status_code=204)
def remove_git_connection(
    connection_id: int,
    _: None = Depends(require_auth),
) -> None:
    try:
        delete_git_connection(connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
