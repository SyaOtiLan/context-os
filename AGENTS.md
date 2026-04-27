# AGENTS.md

This file is the operational briefing for coding agents working on ContextOS.
README.md explains the product. This file explains how to safely modify, run, and
test the repository.

## Project Intent

ContextOS is a local-first personal context system. It is not a companion chatbot
and should not be turned into a vague memory/persona app.

The core workflow is:

```text
raw evidence
-> extraction candidates
-> human review
-> structured profile/projects/artifacts
-> derived profile
-> GitHub issue radar
-> digest/outbox/notifications
```

Important design rule: LLM output must not write directly into final profile or
project tables. It should create reviewable candidates first.

## Setup

Use Python 3.10+.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
python3 scripts/init_db.py
python3 -m pytest -q
```

The default local database is `data/app.db`.

## Configuration

Runtime configuration is read from environment variables and from a local `.env`
file in the repository root. Shell environment variables take precedence over
`.env`.

Common variables:

```text
PCOS_DB_PATH=data/app.db
PCOS_LLM_API_BASE=...
PCOS_LLM_API_KEY=...
PCOS_LLM_MODEL=...
PCOS_LLM_WIRE_API=responses
PCOS_GITHUB_TOKEN=...
PCOS_SMTP_HOST=...
PCOS_SMTP_FROM=...
PCOS_SMTP_TO=...
```

Do not commit real secrets.

## Data Safety

Never commit these:

- `.env`
- `private/`
- `data/*.db`
- resumes, chat exports, raw personal files
- API keys, SMTP passwords, GitHub tokens

These paths are intentionally ignored. Preserve that boundary.

## Common Commands

Initialize the database:

```bash
python3 scripts/init_db.py
```

Import cleaned private evidence:

```bash
python3 scripts/import_private_evidence.py
```

Extract reviewable candidates from existing raw evidence:

```bash
python3 scripts/extract_evidence_candidates.py
```

Review candidates:

```bash
python3 scripts/review_candidates.py list
python3 scripts/review_candidates.py show 1
python3 scripts/review_candidates.py apply 1
python3 scripts/review_candidates.py reject 1
```

Queue a radar digest email:

```bash
python3 scripts/enqueue_radar_digest.py --repo owner/repo
```

Send pending email outbox items:

```bash
python3 scripts/send_outbox.py
```

Run the full radar job for scheduling:

```bash
python3 scripts/run_radar_job.py --repo owner/repo --analysis-limit 5
python3 scripts/run_radar_job.py --repo owner/repo --analysis-limit 5 --send
```

Run the API:

```bash
uvicorn personal_agent.main:app --host 0.0.0.0 --port 5000
```

## Architecture Map

- `personal_agent/schema.sql`: SQLite schema.
- `personal_agent/models.py`: Pydantic models.
- `personal_agent/services/repository.py`: database access layer.
- `personal_agent/services/ingestion.py`: raw evidence to extraction candidates.
- `personal_agent/services/profile_derivation.py`: structured data to derived profile.
- `personal_agent/services/github_issues.py`: GitHub issue sync.
- `personal_agent/services/issue_radar.py`: filtering, LLM analysis, digest, outbox creation.
- `personal_agent/services/notifications.py`: SMTP sender for notification outbox.
- `personal_agent/api/`: FastAPI routers.
- `scripts/`: local operational scripts.
- `tests/`: pytest coverage.

## Development Rules

- Keep raw evidence, review candidates, and final structured data separate.
- Prefer small, test-covered changes.
- Use `Repository` methods for database access instead of inline SQL in API handlers.
- Preserve local-first behavior; do not require external services for basic CRUD/tests.
- If a feature touches LLM, GitHub, SMTP, or private data, keep secrets in `.env`.
- Run `python3 -m pytest -q` before committing.

## Current Product Boundary

High priority:

- ingestion review loop
- derived profile quality
- IssueRadar matching quality
- digest/outbox/SMTP output
- minimal operational scripts

Lower priority for now:

- polished frontend
- multi-user support
- vector database/RAG
- autonomous agent behavior
- companion-style chat
