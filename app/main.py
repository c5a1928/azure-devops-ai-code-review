from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.api.jobs import router as jobs_router
from app.api.git_connections import router as git_connections_router
from app.api.git_projects import router as git_projects_router
from app.api.reviews import router as reviews_router
from app.api.settings import router as settings_router
from app.settings_store import bootstrap_settings

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _frontend_dir() -> Path | None:
    browser_dir = STATIC_DIR / "browser"
    if browser_dir.exists():
        return browser_dir
    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        return STATIC_DIR
    return None


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap_settings()
    yield


app = FastAPI(
    title="PlyRev",
    description="AI-powered pull request reviews for Azure DevOps, GitHub, GitLab, and Bitbucket",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(settings_router)
app.include_router(git_connections_router)
app.include_router(jobs_router)
app.include_router(git_projects_router)
app.include_router(reviews_router)


frontend_dir = _frontend_dir()


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "frontend_built": frontend_dir is not None,
    }


if frontend_dir is None:
    logger.warning(
        "Frontend static files missing under %s — UI routes are disabled. "
        "For production use: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build",
        STATIC_DIR,
    )

    @app.get("/")
    async def frontend_missing() -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Frontend not built or app/static was overwritten by a volume mount. "
                    "Rebuild the image and deploy with docker-compose.prod.yml."
                ),
            },
        )
elif frontend_dir is not None:
    index_file = frontend_dir / "index.html"

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str = "") -> FileResponse:
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path:
            asset = frontend_dir / full_path
            if asset.is_file():
                return FileResponse(asset)
        if not index_file.exists():
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(index_file)
