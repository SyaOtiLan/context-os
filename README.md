# Personal Context OS

Personal Context OS is a local-first backend for turning personal facts, projects, artifacts, and goals into actionable context.

The current MVP focuses on one practical workflow:

```text
structured personal context -> derived profile -> GitHub issue sync/filter/analyze -> recommended opportunities
```

It is not a companion chatbot and it does not depend on a vector database. The core is structured data, explicit rules, SQLite storage, and a small AI layer for issue analysis.

## Current Status

This repo is an early but runnable MVP.

Implemented:

- FastAPI backend backed by SQLite
- profile facts and preferences
- rule-based derived profile snapshots
- projects, artifacts, notes, opportunities, tasks, and policies
- service registry and health probing
- GitHub issue synchronization
- rule-based issue filtering
- LLM-backed issue analysis using the derived profile
- digest-style issue recommendation output
- CLI entrypoint for local use
- pytest coverage for repository, API handlers, profile derivation, ops, CLI, and radar flow

Not implemented yet:

- polished frontend
- scheduler/cron integration
- email/Slack/notification output layer
- multi-user support
- public hosted deployment

## Why This Exists

The project is built around a simple assumption: personal AI tools are more useful when they are grounded in evidence.

Instead of starting from a vague long-term memory or persona, the system stores concrete records:

- what projects exist
- what artifacts were produced
- what facts and preferences are known
- what opportunities were found
- what tasks or policies are active

The derived profile is generated from that lower-level data and can then be consumed by tools such as GitHub issue discovery.

## Project Layout

```text
personal_agent/
  api/          FastAPI routers
  services/     application services, repository, profile derivation, radar pipeline
  config.py     environment-based settings
  db.py         SQLite connection and schema initialization
  main.py       FastAPI app entrypoint
  models.py     Pydantic request/response models
  schema.sql    SQLite schema
scripts/
  init_db.py    initialize SQLite schema
  bootstrap_venv.sh
tests/          pytest coverage
data/
  app.db        default local runtime database
deploy/
  systemd/      example service unit
```

## Quick Start

Install the package in editable mode:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Initialize the database:

```bash
python3 scripts/init_db.py
```

Start the API server:

```bash
uvicorn personal_agent.main:app --host 0.0.0.0 --port 5000
```

Open the API docs:

```text
http://127.0.0.1:5000/docs
```

## Configuration

The default database path is `data/app.db`.

Useful environment variables:

```bash
export PCOS_DB_PATH=data/app.db
export PCOS_GITHUB_TOKEN=...
export PCOS_LLM_API_BASE=https://api.openai.com/v1
export PCOS_LLM_API_KEY=...
export PCOS_LLM_MODEL=...
```

GitHub sync can run without a token for light usage, but authenticated requests are more reliable.

LLM configuration is only required for `/radar/analyze` and `/radar/run`.

## API Surface

Core:

- `GET /health`
- `GET /overview`

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

Ops:

- `GET /ops/services`
- `POST /ops/services`
- `POST /ops/services/{service_id}/checks`
- `POST /ops/services/{service_id}/probe`
- `POST /ops/probe-all`

Radar:

- `POST /radar/sync`
- `POST /radar/filter`
- `POST /radar/analyze`
- `GET /radar/issues`
- `GET /radar/digest`
- `POST /radar/run`
- `POST /radar/mark-alerts`

## Example Radar Flow

Create or update profile context first:

```bash
curl -X POST http://127.0.0.1:5000/profile/facts \
  -H 'content-type: application/json' \
  -d '{"category":"goal","key":"current_focus","value":"Build practical AI developer tools around personal context and GitHub issue discovery."}'
```

Refresh the derived profile:

```bash
curl -X POST http://127.0.0.1:5000/profile/derived/refresh
```

Sync open GitHub issues:

```bash
curl -X POST http://127.0.0.1:5000/radar/sync \
  -H 'content-type: application/json' \
  -d '{"repo":"owner/repo"}'
```

Apply hard filters:

```bash
curl -X POST http://127.0.0.1:5000/radar/filter \
  -H 'content-type: application/json' \
  -d '{"repo":"owner/repo"}'
```

Analyze eligible issues with the derived profile:

```bash
curl -X POST http://127.0.0.1:5000/radar/analyze \
  -H 'content-type: application/json' \
  -d '{"repo":"owner/repo","limit":10}'
```

Read recommendation output:

```bash
curl 'http://127.0.0.1:5000/radar/digest?repo=owner/repo&lookback_days=3'
```

## CLI

Run locally with:

```bash
python -m personal_agent
```

or after editable install:

```bash
pcos
```

Useful first commands:

```bash
pcos home
pcos project add --slug myagent --title "MyAgent"
pcos artifact add --project myagent --artifact-type repo --title "GitHub Repo" --url https://github.com/...
pcos task add --project myagent --title "Wire derived profile into radar"
pcos capture "Today I connected profile derivation with issue discovery." --title daily
pcos service add --name issueradar --service-type http --endpoint https://example.com/health
pcos service probe issueradar
```

## Development

Run tests:

```bash
python3 -m pytest
```

Run static checks when dev dependencies are installed:

```bash
ruff check .
pyright
```

## Deployment

Suggested server layout:

```text
/opt/personal-context-os/
  personal_agent/
  scripts/
  data/
  .venv/
```

Bootstrap on the server:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python scripts/init_db.py
```

Then adapt:

- [`deploy/systemd/personal-context-os.service`](./deploy/systemd/personal-context-os.service)

## Design Notes

- SQLite is the default storage layer.
- Raw facts and derived profile snapshots are kept separate.
- Opportunities are treated as top-level inputs, not profile evidence by default.
- The radar pipeline uses GitHub structured fields first, then limited text heuristics.
- AI is used as an analysis layer, not as the source of truth for the system.
