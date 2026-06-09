from __future__ import annotations

import traceback

from app.celery_app import celery_app
from app.config import get_settings
from app.services.azure_devops import AzureDevOpsClient
from app.services.comment_resolver import CommentResolver
from app.services.email import send_review_notification
from app.services.reviewer import CodeReviewer


@celery_app.task(bind=True, name="app.tasks.review_pull_request")
def review_pull_request(self, repo_name: str, pr_id: int, project: str | None = None) -> dict:
    settings = get_settings()
    project_name = project or settings.azure_devops_project

    client = AzureDevOpsClient(
        base_url=settings.azure_devops_base_url,
        org=settings.azure_devops_org,
        project=project_name,
        pat=settings.azure_devops_pat,
    )
    reviewer = CodeReviewer(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
        reasoning_effort=settings.openai_reasoning_effort,
    )
    comment_resolver = CommentResolver(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
        reasoning_effort=settings.openai_reasoning_effort,
    )

    reviewer_user_id, recipient_email = client.get_authenticated_user()
    pr_url = (
        f"{settings.azure_devops_base_url}/{settings.azure_devops_org}/"
        f"{project_name.replace(' ', '%20')}/_git/{repo_name}/pullrequest/{pr_id}"
    )

    try:
        self.update_state(state="PROGRESS", meta={"step": "fetching_pr"})
        pr = client.get_pull_request(repo_name, pr_id)
        file_diffs = client.get_file_diffs(repo_name, pr)

        self.update_state(state="PROGRESS", meta={"step": "resolving_comments"})
        active_threads = client.list_active_reviewer_threads(repo_name, pr_id, reviewer_user_id)
        thread_ids_to_resolve = comment_resolver.threads_to_resolve(pr, file_diffs, active_threads)
        resolved_thread_ids: list[int] = []
        for thread_id in thread_ids_to_resolve:
            try:
                client.resolve_thread(repo_name, pr_id, thread_id)
                resolved_thread_ids.append(thread_id)
            except Exception:
                continue

        self.update_state(state="PROGRESS", meta={"step": "reviewing"})
        review = reviewer.review(pr, file_diffs)

        self.update_state(state="PROGRESS", meta={"step": "posting_comments"})
        summary_thread_id: int | None = None
        if review.summary:
            summary_thread_id = client.post_summary_comment(repo_name, pr_id, review.summary)
        inline_thread_ids: list[int] = []
        for comment in review.inline_comments:
            thread_id = client.post_inline_comment(
                repo_name,
                pr_id,
                file_path=comment.file_path,
                line=comment.line,
                content=comment.content,
                change_tracking_id=comment.change_tracking_id,
                iteration_id=comment.iteration_id,
                offset_start=comment.offset_start,
                offset_end=comment.offset_end,
            )
            inline_thread_ids.append(thread_id)

        result = {
            "repo_name": repo_name,
            "pr_id": pr_id,
            "project": project_name,
            "title": pr.title,
            "linked_work_items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "type": item.work_item_type,
                    "state": item.state,
                }
                for item in pr.work_items
            ],
            "verdict": review.verdict,
            "detected_frameworks": review.detected_frameworks,
            "llm_model": settings.openai_model,
            "llm_reasoning_effort": settings.openai_reasoning_effort,
            "resolved_thread_ids": resolved_thread_ids,
            "resolved_comment_count": len(resolved_thread_ids),
            "summary_thread_id": summary_thread_id,
            "inline_thread_ids": inline_thread_ids,
            "inline_comment_count": len(inline_thread_ids),
            "pr_url": pr_url,
            "review_diagnostics": _serialize_diagnostics(review.diagnostics),
        }

        self.update_state(state="PROGRESS", meta={"step": "sending_email"})
        try:
            send_review_notification(
                gmail_user=settings.gmail_user,
                gmail_app_password=settings.gmail_app_password,
                recipient=recipient_email,
                subject=f"PR review complete: {repo_name} #{pr_id} — {pr.title}",
                body_text=_build_email_text(result),
                body_html=_build_email_html(result),
            )
            result["notification_sent_to"] = recipient_email
        except Exception as email_exc:
            result["notification_sent_to"] = None
            result["notification_error"] = (
                f"{type(email_exc).__name__}: {email_exc}. "
                "Review comments were still posted to the PR."
            )
        return result

    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        try:
            send_review_notification(
                gmail_user=settings.gmail_user,
                gmail_app_password=settings.gmail_app_password,
                recipient=recipient_email,
                subject=f"PR review failed: {repo_name} #{pr_id}",
                body_text=(
                    f"The automated PR review failed.\n\n"
                    f"Repository: {repo_name}\n"
                    f"PR ID: {pr_id}\n"
                    f"URL: {pr_url}\n\n"
                    f"Error: {error_message}\n\n"
                    f"{traceback.format_exc()}"
                ),
            )
        except Exception:
            pass
        raise


def _serialize_diagnostics(diagnostics) -> dict | None:
    if diagnostics is None:
        return None
    return {
        "llm_verdict": diagnostics.llm_verdict,
        "llm_inline_count": diagnostics.llm_inline_count,
        "parsed_inline_count": diagnostics.parsed_inline_count,
        "dropped_inline_count": diagnostics.dropped_inline_count,
        "drop_reasons": diagnostics.drop_reasons,
        "warnings": diagnostics.warnings,
    }


def _build_email_text(result: dict) -> str:
    comments_posted = result["inline_comment_count"] + (1 if result.get("summary_thread_id") else 0)
    diagnostics = result.get("review_diagnostics") or {}
    warnings = diagnostics.get("warnings") or []
    warning_block = ""
    if warnings:
        warning_block = "\nWarnings:\n" + "\n".join(f"- {item}" for item in warnings) + "\n"

    diagnostics_block = ""
    if diagnostics:
        diagnostics_block = (
            f"\nLLM inline comments: {diagnostics.get('llm_inline_count', 0)}\n"
            f"Parsed inline comments: {diagnostics.get('parsed_inline_count', 0)}\n"
            f"Dropped inline comments: {diagnostics.get('dropped_inline_count', 0)}\n"
        )

    return (
        f"PR review completed.\n\n"
        f"Repository: {result['repo_name']}\n"
        f"PR: #{result['pr_id']}\n"
        f"Title: {result['title']}\n"
        f"Verdict: {result['verdict']}\n"
        f"Comments posted: {comments_posted}\n"
        f"Comments resolved: {result.get('resolved_comment_count', 0)}"
        f"{diagnostics_block}"
        f"{warning_block}"
        f"PR URL: {result['pr_url']}\n"
    )


def _build_email_diagnostics_html(diagnostics: dict | None) -> str:
    if not diagnostics:
        return ""
    warnings = diagnostics.get("warnings") or []
    warning_items = "".join(f"<li>{item}</li>" for item in warnings)
    warnings_html = f"<ul>{warning_items}</ul>" if warning_items else "<p>None</p>"
    return f"""
        <h3>Review diagnostics</h3>
        <ul>
          <li><strong>LLM inline comments:</strong> {diagnostics.get('llm_inline_count', 0)}</li>
          <li><strong>Parsed inline comments:</strong> {diagnostics.get('parsed_inline_count', 0)}</li>
          <li><strong>Dropped inline comments:</strong> {diagnostics.get('dropped_inline_count', 0)}</li>
        </ul>
        <p><strong>Warnings</strong></p>
        {warnings_html}
    """


def _build_email_html(result: dict) -> str:
    return f"""
    <html>
      <body>
        <h2>PR review completed</h2>
        <ul>
          <li><strong>Repository:</strong> {result['repo_name']}</li>
          <li><strong>PR:</strong> #{result['pr_id']}</li>
          <li><strong>Title:</strong> {result['title']}</li>
          <li><strong>Verdict:</strong> {result['verdict']}</li>
          <li><strong>Comments posted:</strong> {result['inline_comment_count'] + (1 if result.get('summary_thread_id') else 0)}</li>
          <li><strong>Comments resolved:</strong> {result.get('resolved_comment_count', 0)}</li>
        </ul>
        {_build_email_diagnostics_html(result.get('review_diagnostics'))}
        <p><a href="{result['pr_url']}">View pull request</a></p>
      </body>
    </html>
    """
