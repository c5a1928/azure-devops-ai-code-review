# Azure DevOps AI Code Review

Automated pull request reviews for **Azure DevOps** using an OpenAI-compatible LLM. Trigger a review via HTTP; a background worker fetches the PR diff, linked work items, and acceptance criteria, runs a strict senior-engineer-style review, and posts inline comments back to the PR.

## Features

- **Work-item-aware reviews** — checks changes against linked Azure DevOps work items and acceptance criteria
- **Inline comments** — up to 8 anchored comments on changed lines with code snippets
- **Framework detection** — applies stack-specific checks for FastAPI, Flask, SQLAlchemy, Pydantic, Celery, and Django
- **Comment resolution** — on re-review, auto-resolves prior reviewer threads when issues are fixed
- **Email notification** — optional Gmail summary when a review completes
- **Any OpenAI-compatible API** — works with OpenAI, Azure OpenAI, or local proxies via `OPENAI_BASE_URL`
- **Reasoning models** — supports GPT-5.x with configurable `OPENAI_REASONING_EFFORT`

## Architecture

```
POST /review  →  FastAPI  →  Celery task  →  Redis
                                ↓
                    Azure DevOps API (PR, diffs, work items, comments)
                                ↓
                    OpenAI-compatible LLM
                                ↓
                    Post comments + email notification
```

| Service | Role | Default port |
|---------|------|--------------|
| `api` | FastAPI HTTP API | 8090 |
| `worker` | Celery review worker | — |
| `redis` | Task broker | 6380 (host) |

## Prerequisites

- Docker and Docker Compose
- Azure DevOps [Personal Access Token](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate) with **Code (Read & Write)** and **Work Items (Read)** scopes
- OpenAI API key (or compatible endpoint)
- Gmail app password (optional, for email notifications)

## Quick start

1. **Clone and configure**

   ```bash
   git clone git@github.com:c5a1928/azure-devops-ai-code-review.git
   cd azure-devops-ai-code-review
   cp .env.example .env
   # Edit .env with your Azure DevOps and OpenAI credentials
   ```

2. **Start services**

   ```bash
   docker compose up -d --build
   ```

3. **Trigger a review**

   ```bash
   curl -X POST http://localhost:8090/review \
     -H "Content-Type: application/json" \
     -d '{"repo_name": "my-service", "pr_id": 42}'
   ```

   Response (202):

   ```json
   {
     "task_id": "abc-123",
     "status": "queued",
     "message": "Review queued for my-service PR #42"
   }
   ```

4. **Poll task status**

   ```bash
   curl http://localhost:8090/review/abc-123
   ```

   A Postman collection is included in [`postman/`](postman/).

## Configuration

Copy [`.env.example`](.env.example) to `.env`. Never commit `.env`.

| Variable | Description |
|----------|-------------|
| `AZURE_DEVOPS_ORG` | Organization name (e.g. `contoso`) |
| `AZURE_DEVOPS_PROJECT` | Default project name |
| `AZURE_DEVOPS_PAT` | Personal access token |
| `OPENAI_API_KEY` | API key for the LLM provider |
| `OPENAI_BASE_URL` | API base URL (default: `https://api.openai.com/v1`) |
| `OPENAI_MODEL` | Model slug (default: `gpt-5.5`) |
| `OPENAI_REASONING_EFFORT` | For reasoning models: `none`, `low`, `medium`, `high`, `xhigh` |
| `OPENAI_MAX_TOKENS` | Max completion tokens including internal reasoning (default: `16384`) |
| `OPENAI_TEMPERATURE` | Used when `OPENAI_REASONING_EFFORT` is unset |
| `GMAIL_USER` | Sender address for notifications |
| `GMAIL_APP_PASSWORD` | [Google app password](https://myaccount.google.com/apppasswords) |

### Model recommendations

| Model | Trade-off |
|-------|-----------|
| `gpt-5.5` + `high` | Best review quality; slower and higher cost |
| `gpt-5.4-mini` | Good balance of speed and quality |
| `gpt-4o` | Cheaper; less thorough on complex PRs |

LLM usage is billed by your provider. Large PRs with `gpt-5.5` and high reasoning effort can cost noticeably more per review than `gpt-4o-mini`.

## API

### `GET /health`

Returns `{"status": "ok"}`.

### `POST /review`

Queue a PR review.

**Body:**

```json
{
  "repo_name": "my-service",
  "pr_id": 42,
  "project": "My Project"
}
```

`project` is optional and defaults to `AZURE_DEVOPS_PROJECT`.

### `GET /review/{task_id}`

Returns task status: `pending`, `in_progress`, `completed`, or `failed`.

Completed results include `verdict`, `inline_comment_count`, `linked_work_items`, `detected_frameworks`, `llm_model`, and `review_diagnostics`.

## What the reviewer checks

1. **Functional / logical** — alignment with linked work items and acceptance criteria
2. **Efficiency** — N+1 queries, wasteful patterns, unnecessary work
3. **Python 3 / PEP** — on changed `.py` lines
4. **Framework idioms** — when FastAPI, Flask, SQLAlchemy, Pydantic, Celery, or Django is detected

Reviews are written as plain prose from a strict senior engineer: specific issues, code snippets, impact, and concrete fixes. No compliments, no LGTM-only comments, and no mention of automation.

## Local development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Terminal 1 — Redis (or use docker compose up redis -d)
redis-server

# Terminal 2 — Celery worker
celery -A app.celery_app.celery_app worker --loglevel=info

# Terminal 3 — API
uvicorn app.main:app --reload --port 8090
```

## Security notes

- Store secrets only in `.env` or your deployment secret manager
- The PAT is used to post comments as the token owner — use a dedicated service account if possible
- Rotate credentials if they are ever exposed
- Review LLM output before treating it as authoritative; it can miss issues or flag false positives

## License

MIT — see [LICENSE](LICENSE).
