# ContextOS

Most GitHub issue finders ask:

```text
Which issues are open?
```

ContextOS asks a more useful question:

```text
Which issues are actually worth doing for me?
```

It builds a reviewed personal profile from your projects, notes, resume, articles,
and other evidence, then uses that profile to scan GitHub issues and email you a
digest of opportunities that match your current goals.

## Example Output

```text
[ContextOS Radar] vllm-project/vllm: 6 digest items

Watchlist
- vllm-project/vllm#XXXXX [7/10, medium] Improve scheduler test coverage
  Why fit: matches Python, AI infrastructure, and test-focused contribution goals.
  Why not: requires understanding part of the scheduling path first.
  First step: reproduce the issue and inspect the existing scheduler tests.

Screened out
- vllm-project/vllm#YYYYY Large distributed runtime refactor
  Reasons: already assigned, large refactor, not a good first contribution.
```

The point is not to let an agent randomly browse GitHub. The point is to turn
your own context into a practical filter for what to work on next.

## What It Does

- stores raw evidence about you and your work
- asks an LLM to extract reviewable profile/project/artifact candidates
- requires human confirmation before writing final profile data
- derives a compact profile from confirmed facts
- syncs and filters GitHub issues using structured fields first
- uses the derived profile to analyze issue fit
- queues and sends an email digest through SMTP

## Why Not Just Use an Agent?

ContextOS is deliberately not an autonomous multi-agent system.

The current workflow is a controlled pipeline:

```text
raw evidence
-> extraction candidates
-> human review
-> structured profile/projects/artifacts
-> derived profile
-> GitHub issue radar
-> email digest
```

LLM output never writes directly into the final profile. It creates candidates
that can be applied or rejected. This keeps the system inspectable and prevents a
bad extraction from silently polluting future recommendations.

## Current Status

ContextOS is an early but runnable MVP. It has already replaced a standalone
IssueRadar workflow for scheduled GitHub issue digests.

Implemented:

- SQLite-backed FastAPI service
- raw evidence and review-before-write extraction candidates
- profile facts, preferences, projects, artifacts, notes, opportunities, tasks, and policies
- derived profile snapshots
- GitHub issue sync, filtering, LLM analysis, and digest generation
- notification outbox and SMTP email sender
- operational scripts for ingestion, review, radar jobs, and email sending
- `AGENTS.md` for coding agents and maintainers
- pytest coverage across repository, API handlers, ingestion, profile derivation, radar, notifications, and scripts

Not the focus yet:

- polished frontend
- multi-user hosting
- vector database/RAG
- autonomous agent behavior

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

Start the API:

```bash
uvicorn personal_agent.main:app --host 0.0.0.0 --port 5000
```

Open:

```text
http://127.0.0.1:5000/docs
```

If you use a coding agent to set up the repository, ask it to read
[`AGENTS.md`](./AGENTS.md) first.

## Core Commands

Import cleaned evidence:

```bash
python3 scripts/import_private_evidence.py
```

Extract reviewable candidates:

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

Run a radar job:

```bash
python3 scripts/run_radar_job.py --repo owner/repo --analysis-limit 5
```

Run radar and send email:

```bash
python3 scripts/run_radar_job.py --repo owner/repo --analysis-limit 5 --send
```

## Configuration

Copy `.env.example` to `.env` and fill only what you need.

LLM configuration is required for extraction and radar analysis:

```bash
PCOS_LLM_API_BASE=https://api.openai.com/v1
PCOS_LLM_API_KEY=...
PCOS_LLM_MODEL=gpt-4.1
PCOS_LLM_WIRE_API=responses
```

GitHub token is optional but recommended:

```bash
PCOS_GITHUB_TOKEN=...
```

SMTP is required only for email delivery:

```bash
PCOS_SMTP_HOST=smtp.example.com
PCOS_SMTP_USERNAME=...
PCOS_SMTP_PASSWORD=...
PCOS_SMTP_FROM=contextos@example.com
PCOS_SMTP_TO=you@example.com
```

Do not commit `.env`, local databases, or private evidence.

## Architecture

```text
personal_agent/
  api/          FastAPI routers
  services/     repository, ingestion, profile derivation, radar, notifications
  config.py     env and .env based settings
  db.py         SQLite connection and schema initialization
  models.py     Pydantic models
  schema.sql    SQLite schema
scripts/
  import_private_evidence.py
  extract_evidence_candidates.py
  review_candidates.py
  run_radar_job.py
  send_outbox.py
docs/
  API and deployment notes
```

More details:

- [API reference](./docs/api.md)
- [Deployment notes](./docs/deployment.md)

## Design Principles

- Store evidence first; derive summaries later.
- Keep raw evidence, candidates, and final structured data separate.
- Use LLMs for extraction and judgment, not as the source of truth.
- Prefer deterministic pipeline steps over autonomous agent behavior.
- Make outputs auditable: candidates, analyses, digest items, and email outbox are stored.

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
