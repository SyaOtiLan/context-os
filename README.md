# ContextOS

ContextOS is a local-first personal context system that turns evidence about your
projects, skills, goals, and work history into actionable recommendations.

The current MVP is built around one concrete workflow:

```text
raw evidence
-> AI extraction candidates
-> human review
-> structured profile/projects/artifacts
-> derived profile
-> GitHub issue radar
-> digest email
```

It is not a companion chatbot, not a generic agent framework, and not a vector
database demo. The core idea is simpler: keep personal context structured,
reviewable, and useful for real decisions.

## Why This Exists

Finding GitHub issues to work on is not just a search problem. The useful
question is:

```text
Which issue is worth doing for me, given what I have built, learned, and want to improve?
```

ContextOS answers that by separating evidence from derived conclusions:

- store raw evidence first, such as resumes, project notes, repo summaries, and articles
- let an LLM extract reviewable candidates
- confirm or reject candidates before they become official profile data
- generate a derived profile from confirmed facts and projects
- use that profile to analyze GitHub issues and send a digest

The system is intentionally conservative: AI output is useful, but it is not the
source of truth until reviewed.

## Current Status

This is an early but runnable MVP. It has been deployed and used as a replacement
for a standalone IssueRadar workflow.

Implemented:

- SQLite-backed FastAPI service
- raw evidence storage
- review-before-write extraction candidates
- profile facts, preferences, projects, artifacts, notes, opportunities, tasks, and policies
- rule-based derived profile snapshots
- GitHub issue sync, filtering, LLM analysis, and digest generation
- notification outbox and SMTP email sender
- local operational scripts for ingestion, review, radar jobs, and email sending
- `AGENTS.md` for coding agents and maintainers
- pytest coverage for repository, API handlers, ingestion, profile derivation, radar, notifications, and scripts

Not the focus yet:

- polished frontend
- multi-user hosting
- Slack/webhook output
- vector database/RAG
- autonomous multi-agent behavior

## Quick Start

Use Python 3.10+.

```bash
git clone https://github.com/SyaOtiLan/context-os.git
cd context-os
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
python3 scripts/init_db.py
python3 -m pytest -q
```

Start the API server:

```bash
uvicorn personal_agent.main:app --host 0.0.0.0 --port 5000
```

Open:

```text
http://127.0.0.1:5000/docs
```

If you use a coding agent to set up the repository, ask it to read
[`AGENTS.md`](./AGENTS.md) first.

## Configuration

The default local database is:

```text
data/app.db
```

Configuration is read from environment variables and from `.env`. Shell
environment variables take precedence over `.env`.

Minimal local config:

```bash
PCOS_DB_PATH=data/app.db
```

LLM config is required for candidate extraction and issue analysis:

```bash
PCOS_LLM_API_BASE=https://api.openai.com/v1
PCOS_LLM_API_KEY=...
PCOS_LLM_MODEL=gpt-4.1
PCOS_LLM_WIRE_API=responses
PCOS_LLM_REASONING_EFFORT=low
PCOS_LLM_DISABLE_RESPONSE_STORAGE=true
```

GitHub token is optional but recommended:

```bash
PCOS_GITHUB_TOKEN=...
PCOS_GITHUB_ONLY_PRIORITY_LABELS=true
PCOS_GITHUB_MAX_ISSUE_STALENESS_DAYS=30
```

SMTP config is required only if you want digest emails:

```bash
PCOS_SMTP_HOST=smtp.example.com
PCOS_SMTP_PORT=587
PCOS_SMTP_USERNAME=...
PCOS_SMTP_PASSWORD=...
PCOS_SMTP_FROM=contextos@example.com
PCOS_SMTP_TO=you@example.com
PCOS_SMTP_USE_TLS=true
```

Do not commit `.env`, local databases, or private evidence.

## Core Workflows

Import cleaned private evidence:

```bash
python3 scripts/import_private_evidence.py
```

Extract candidates from existing raw evidence:

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

Run a full radar job:

```bash
python3 scripts/run_radar_job.py --repo owner/repo --analysis-limit 5
```

Run radar and send email:

```bash
python3 scripts/run_radar_job.py --repo owner/repo --analysis-limit 5 --send
```

Queue and send a digest separately:

```bash
python3 scripts/enqueue_radar_digest.py --repo owner/repo
python3 scripts/send_outbox.py
```

## Project Layout

```text
personal_agent/
  api/          FastAPI routers
  services/     repository, ingestion, profile derivation, radar, notifications
  config.py     env and .env based settings
  db.py         SQLite connection and schema initialization
  main.py       FastAPI app entrypoint
  models.py     Pydantic request/response models
  schema.sql    SQLite schema
scripts/
  init_db.py
  import_private_evidence.py
  extract_evidence_candidates.py
  review_candidates.py
  enqueue_radar_digest.py
  run_radar_job.py
  send_outbox.py
tests/
  pytest coverage
deploy/
  systemd/      example service unit
```

## API Surface

Core:

- `GET /health`
- `GET /overview`

Ingestion:

- `POST /ingest/extract`
- `GET /ingest/candidates`
- `POST /ingest/candidates/{candidate_id}/apply`
- `POST /ingest/candidates/{candidate_id}/reject`

Profile:

- `GET /profile/summary`
- `POST /profile/facts`
- `POST /profile/preferences`
- `GET /profile/derived`
- `POST /profile/derived/refresh`
- `GET /profile/derived/latest`

Personal context:

- `GET /projects`
- `POST /projects`
- `GET /artifacts`
- `POST /artifacts`
- `GET /notes`
- `POST /notes`
- `GET /opportunities`
- `POST /opportunities`
- `GET /tasks`
- `POST /tasks`
- `GET /policies`
- `POST /policies`

Radar:

- `POST /radar/sync`
- `POST /radar/filter`
- `POST /radar/analyze`
- `GET /radar/issues`
- `GET /radar/digest`
- `POST /radar/run`
- `POST /radar/mark-alerts`

Ops:

- `GET /ops/services`
- `POST /ops/services`
- `POST /ops/services/{service_id}/checks`
- `POST /ops/services/{service_id}/probe`
- `POST /ops/probe-all`

## CLI

After editable install:

```bash
contextos
```

The short alias also exists:

```bash
pcos
```

Examples:

```bash
pcos home
pcos project add --slug context-os --title "ContextOS"
pcos artifact add --project context-os --artifact-type repo --title "GitHub Repo" --url https://github.com/SyaOtiLan/context-os
pcos capture "Connected profile derivation with issue discovery." --title daily
```

## Development

Run tests:

```bash
python3 -m pytest -q
```

Run static checks when dev dependencies are installed:

```bash
ruff check .
pyright
```

## Deployment

Suggested server layout:

```text
/opt/context-os/
  personal_agent/
  scripts/
  data/
  .venv/
```

Bootstrap:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python scripts/init_db.py
```

Then adapt:

- [`deploy/systemd/context-os.service`](./deploy/systemd/context-os.service)

For scheduled radar emails, run `scripts/run_radar_job.py` from cron or a
systemd timer.

## Design Notes

- SQLite is the default storage layer.
- Raw evidence and derived profile snapshots are separate.
- LLM extraction is review-before-write.
- Opportunities are treated as top-level inputs, not profile evidence by default.
- The radar pipeline uses GitHub structured fields first, then limited text heuristics.
- AI is used as an analysis layer, not as the source of truth.
