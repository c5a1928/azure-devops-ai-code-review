from __future__ import annotations

from pathlib import Path

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_infrastructure_settings
from app.models import Base

_engine = None
SessionLocal: sessionmaker[Session] | None = None


def _resolve_database_url() -> str:
    url = get_infrastructure_settings().database_url
    if url.startswith("sqlite:///"):
        relative = url.removeprefix("sqlite:///")
        if relative.startswith("./"):
            db_path = Path(relative)
            db_path.parent.mkdir(parents=True, exist_ok=True)
    return url


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


def get_engine():
    global _engine, SessionLocal
    if _engine is None:
        url = _resolve_database_url()
        _engine = create_engine(url, **_engine_kwargs(url))
        SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def get_db_session() -> Session:
    if SessionLocal is None:
        get_engine()
    assert SessionLocal is not None
    return SessionLocal()


@contextmanager
def db_session():
    session = get_db_session()
    try:
        yield session
    finally:
        session.close()
