from __future__ import annotations

from dataclasses import dataclass

from app.services.git.types import FileDiff


@dataclass(frozen=True)
class FrameworkProfile:
    name: str
    signals: tuple[str, ...]


# Use import-anchored signals to avoid false positives from generic tokens
# like Column(, select(, or Field( appearing in unrelated code.
FRAMEWORK_PROFILES: tuple[FrameworkProfile, ...] = (
    FrameworkProfile(
        "FastAPI",
        ("from fastapi", "import fastapi", "fastapi.", "apirouter", "fastapi("),
    ),
    FrameworkProfile(
        "Flask",
        ("from flask", "import flask", "flask(", "@app.route", "@blueprint."),
    ),
    FrameworkProfile(
        "SQLAlchemy",
        (
            "from sqlalchemy",
            "import sqlalchemy",
            "declarative_base",
            "mapped_column",
            "mapped[",
            "session.query",
            "relationship(",
        ),
    ),
    FrameworkProfile(
        "Pydantic",
        ("from pydantic", "import pydantic", "basemodel", "model_validate", "configdict"),
    ),
    FrameworkProfile(
        "Celery",
        ("from celery", "import celery", "celery(", "@celery", ".delay(", ".apply_async("),
    ),
    FrameworkProfile(
        "Django",
        ("from django", "import django", "django.db", "models.model"),
    ),
)


FRAMEWORK_CHECKLIST: dict[str, tuple[str, ...]] = {
    "FastAPI": (
        "Use Pydantic models and response_model — flag raw dict/request.json parsing.",
        "Use Depends() for DB sessions — flag manual session lifecycle in handlers.",
        "Keep route handlers thin; flag blocking DB in async routes.",
    ),
    "Flask": (
        "Validate request input before persistence — flag raw request.form/args/json.",
        "Keep SQLAlchemy session commit/rollback consistent in changed routes.",
    ),
    "SQLAlchemy": (
        "Prefer ORM/query builder over raw SQL strings in changed code.",
        "Flag N+1 patterns and FK/relationship definitions that diverge from schema.",
        "Keep session boundaries clear — flag leaks or partial commits.",
    ),
    "Pydantic": (
        "Use models at API/config boundaries — flag unchecked dict/Any for structured data.",
        "Add Field constraints for external input introduced in the diff.",
    ),
    "Celery": (
        "Tasks must be idempotent and use primitive task args, not ORM objects.",
        "Open/close DB sessions inside the worker task.",
    ),
    "Django": (
        "Use ORM with select_related/prefetch_related — flag N+1 queryset loops.",
        "Validate request data before writing models.",
    ),
}


def detect_frameworks(file_diffs: list[FileDiff]) -> list[str]:
    corpus = _build_detection_corpus(file_diffs)
    detected: list[str] = []

    for profile in FRAMEWORK_PROFILES:
        if any(signal in corpus for signal in profile.signals):
            detected.append(profile.name)

    return detected


def build_framework_review_section(file_diffs: list[FileDiff]) -> tuple[list[str], str]:
    frameworks = detect_frameworks(file_diffs)
    if not frameworks:
        return frameworks, ""

    lines = [
        "Framework maintainability (REQUIRED — violations in changed code must be reported):",
        f"Detected stacks: {', '.join(frameworks)}",
    ]
    for framework in frameworks:
        for bullet in FRAMEWORK_CHECKLIST.get(framework, ()):
            lines.append(f"- [{framework}] {bullet}")

    lines.append(
        "- Framework-specific problems are valid findings. Include them in inline_comments "
        "with verdict \"critical\" — do not skip them because logic/PEP checks also ran."
    )
    return frameworks, "\n".join(lines)


def _build_detection_corpus(file_diffs: list[FileDiff]) -> str:
    chunks: list[str] = []
    for item in file_diffs:
        chunks.append(item.path.lower())
        for line in item.new_content.splitlines()[:80]:
            stripped = line.strip().lower()
            if stripped.startswith(("import ", "from ")):
                chunks.append(stripped)
        for line in item.diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                chunks.append(line[1:].lower())
    return "\n".join(chunks)
