from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import inspect, text

from celery.result import AsyncResult

from app.celery_app import celery_app
from app.db import db_session, get_engine, init_db
from app.models import ReviewJobRecord
from app.schemas import ReviewJobPublic


def _now() -> datetime:
    return datetime.now(UTC)


def _record_to_public(record: ReviewJobRecord) -> ReviewJobPublic:
    return ReviewJobPublic(
        task_id=record.task_id,
        git_project_id=record.git_project_id,
        display_path=record.display_path,
        platform=record.platform,
        repo_name=record.repo_name,
        pr_id=record.pr_id,
        status=record.status,
        step=record.step or None,
        error=record.error or None,
        pr_url=record.pr_url or None,
        title=record.title or None,
        verdict=record.verdict or None,
        created_at=record.created_at,
        updated_at=record.updated_at,
        completed_at=record.completed_at,
        archived_at=record.archived_at,
    )


def _merge_celery_status(record: ReviewJobRecord) -> ReviewJobPublic:
    job = _record_to_public(record)
    if job.status in ("completed", "failed"):
        return job

    result = AsyncResult(record.task_id, app=celery_app)
    if result.state == "PENDING":
        job.status = "pending"
        return job
    if result.state == "PROGRESS":
        job.status = "in_progress"
        if isinstance(result.info, dict):
            step = result.info.get("step")
            if isinstance(step, str):
                job.step = step
        return job
    if result.state == "SUCCESS":
        payload = result.result if isinstance(result.result, dict) else {}
        job.status = "completed"
        job.pr_url = payload.get("pr_url") or job.pr_url
        job.title = payload.get("title") or job.title
        job.verdict = payload.get("verdict") or job.verdict
        job.result = payload
        _persist_terminal_state(record, status="completed", result=payload)
        return job
    if result.state == "FAILURE":
        job.status = "failed"
        job.error = str(result.info)
        _persist_terminal_state(record, status="failed", error=job.error)
        return job

    return job


def _persist_terminal_state(
    record: ReviewJobRecord,
    *,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    if record.status in ("completed", "failed"):
        return
    with db_session() as session:
        stored = session.get(ReviewJobRecord, record.task_id)
        if stored is None or stored.status in ("completed", "failed"):
            return
        stored.status = status
        stored.updated_at = _now()
        stored.completed_at = _now()
        if result:
            stored.pr_url = str(result.get("pr_url") or "")
            stored.title = str(result.get("title") or "")
            stored.verdict = str(result.get("verdict") or "")
        if error:
            stored.error = error
        session.add(stored)
        session.commit()


def ensure_jobs_table() -> None:
    init_db()
    migrate_review_jobs_schema()


def migrate_review_jobs_schema() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    if "review_jobs" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("review_jobs")}
    if "archived_at" not in existing:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE review_jobs ADD COLUMN archived_at TIMESTAMPTZ"))


def create_review_job(
    *,
    task_id: str,
    git_project_id: int,
    display_path: str,
    platform: str,
    repo_name: str,
    pr_id: int,
) -> ReviewJobPublic:
    with db_session() as session:
        record = ReviewJobRecord(
            task_id=task_id,
            git_project_id=git_project_id,
            display_path=display_path,
            platform=platform,
            repo_name=repo_name,
            pr_id=pr_id,
            status="pending",
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return _record_to_public(record)


def list_review_jobs(*, limit: int = 50, include_archived: bool = False) -> list[ReviewJobPublic]:
    with db_session() as session:
        query = session.query(ReviewJobRecord)
        if not include_archived:
            query = query.filter(ReviewJobRecord.archived_at.is_(None))
        records = (
            query.order_by(ReviewJobRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_merge_celery_status(record) for record in records]


def get_review_job(task_id: str) -> ReviewJobPublic | None:
    with db_session() as session:
        record = session.get(ReviewJobRecord, task_id)
        if record is None:
            return None
        job = _merge_celery_status(record)
        if job.status == "completed" and job.result is None and record.status == "completed":
            result = AsyncResult(task_id, app=celery_app)
            if result.state == "SUCCESS" and isinstance(result.result, dict):
                job.result = result.result
        return job


def mark_job_in_progress(task_id: str) -> None:
    with db_session() as session:
        record = session.get(ReviewJobRecord, task_id)
        if record is None:
            return
        record.status = "in_progress"
        record.updated_at = _now()
        session.add(record)
        session.commit()


def mark_job_step(task_id: str, step: str) -> None:
    with db_session() as session:
        record = session.get(ReviewJobRecord, task_id)
        if record is None:
            return
        record.status = "in_progress"
        record.step = step
        record.updated_at = _now()
        session.add(record)
        session.commit()


def mark_job_completed(task_id: str, result: dict) -> None:
    with db_session() as session:
        record = session.get(ReviewJobRecord, task_id)
        if record is None:
            return
        record.status = "completed"
        record.step = ""
        record.pr_url = str(result.get("pr_url") or "")
        record.title = str(result.get("title") or "")
        record.verdict = str(result.get("verdict") or "")
        record.updated_at = _now()
        record.completed_at = _now()
        session.add(record)
        session.commit()


def mark_job_failed(task_id: str, error: str) -> None:
    with db_session() as session:
        record = session.get(ReviewJobRecord, task_id)
        if record is None:
            return
        record.status = "failed"
        record.error = error
        record.updated_at = _now()
        record.completed_at = _now()
        session.add(record)
        session.commit()


def archive_review_job(task_id: str) -> ReviewJobPublic:
    with db_session() as session:
        record = session.get(ReviewJobRecord, task_id)
        if record is None:
            raise LookupError("Job not found.")
        record.archived_at = _now()
        record.updated_at = _now()
        session.add(record)
        session.commit()
        session.refresh(record)
        return _record_to_public(record)


def unarchive_review_job(task_id: str) -> ReviewJobPublic:
    with db_session() as session:
        record = session.get(ReviewJobRecord, task_id)
        if record is None:
            raise LookupError("Job not found.")
        record.archived_at = None
        record.updated_at = _now()
        session.add(record)
        session.commit()
        session.refresh(record)
        return _record_to_public(record)


def delete_review_job(task_id: str) -> None:
    with db_session() as session:
        record = session.get(ReviewJobRecord, task_id)
        if record is None:
            raise LookupError("Job not found.")
        session.delete(record)
        session.commit()
