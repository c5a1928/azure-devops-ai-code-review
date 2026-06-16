# PlyRev

Automated pull request reviews for **Azure DevOps, GitHub, GitLab, and Bitbucket** using an OpenAI-compatible LLM. Configure integrations in a Firebase-style web console, then trigger reviews that post inline comments back to the PR.

**Live UI:** http://localhost:8090 (after `docker compose up`)

## Features

- **Firebase-style console** — light sidebar navigation, integration cards, clean forms
- **Multi-platform git** — Azure DevOps, GitHub, GitLab, Bitbucket (self-hosted URLs supported)
- **Work-item-aware reviews** — Azure DevOps linked work items and acceptance criteria
- **Inline comments** — up to 8 anchored comments on changed lines with code snippets
- **Framework detection** — FastAPI, Flask, SQLAlchemy, Pydantic, Celery, Django
- **Comment resolution** — auto-resolves prior threads on Azure DevOps re-reviews
- **Email notification** — optional Gmail summary when a review completes
- **Reasoning models** — GPT-5.x with configurable `OPENAI_REASONING_EFFORT`

## Supported git platforms

| Platform | API default | Notes |
|----------|-------------|-------|
| Azure DevOps | `https://dev.azure.com` | Work items, thread resolution, full inline anchoring |
| GitHub | `https://api.github.com` | PR reviews and inline comments |
| GitLab | `https://gitlab.com/api/v4` | Merge request discussions |
| Bitbucket | `https://api.bitbucket.org/2.0` | Pull request comments |

## Quick start

```bash
git clone git@github.com:c5a1928/azure-devops-ai-code-review.git
cd azure-devops-ai-code-review
cp .env.example .env
docker compose up -d --build
```

This starts **PostgreSQL**, **Keycloak 26**, Redis, the API, and the Celery worker. Settings are stored in Postgres (`pg_data` volume).

Open http://localhost:8090 and **Sign in** or **Sign up** via Keycloak.

| Service | URL |
|---------|-----|
| App | http://localhost:8090 |
| Keycloak admin | http://localhost:8081 (admin / admin) |
| Postgres | localhost:5433 |

### Authentication

Users sign in through **Keycloak 26** (`plyrev` realm). Registration is enabled on the login screen.

Use **http://localhost:8081** for Keycloak (not `127.0.0.1`) — the hostname is configured for `localhost`. Admin console: http://localhost:8081/admin/ (admin / admin).

To disable Keycloak and use the legacy admin password instead:

```env
KEYCLOAK_ENABLED=false
ADMIN_PASSWORD=your-secret
```

1. **Integrations → Git platform** — pick a provider and save credentials
2. **Integrations → AI model** — add your LLM API key
3. **Run review** — enter repository and PR/MR ID

## Console sections

| Page | Purpose |
|------|---------|
| Run review | Queue a PR review and watch progress |
| Git platform | Select Azure DevOps, GitHub, GitLab, or Bitbucket |
| AI model | OpenAI-compatible LLM settings |
| Notifications | Optional Gmail completion emails |

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/platforms` | List supported git platforms |
| `GET` | `/api/settings` | Read configuration |
| `PUT` | `/api/settings` | Save configuration |
| `POST` | `/api/review` | Queue a review |
| `GET` | `/api/review/{task_id}` | Poll status |

## Local development

### Backend

Requires PostgreSQL. With Docker Compose, Postgres is exposed on `localhost:5433`.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# ensure DATABASE_URL points at Postgres (see .env.example)
uvicorn app.main:app --reload --port 8090
celery -A app.celery_app.celery_app worker --loglevel=info
```

### Frontend (Angular)

```bash
cd frontend
npm install
npm run build
npm start   # :4200 with API proxy
```

## License

MIT — see [LICENSE](LICENSE).
