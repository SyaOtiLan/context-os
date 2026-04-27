# API Reference

Run the server:

```bash
uvicorn personal_agent.main:app --host 0.0.0.0 --port 5000
```

Open the interactive docs:

```text
http://127.0.0.1:5000/docs
```

## Core

- `GET /health`
- `GET /overview`

## Ingestion

- `POST /ingest/extract`
- `GET /ingest/candidates`
- `POST /ingest/candidates/{candidate_id}/apply`
- `POST /ingest/candidates/{candidate_id}/reject`

## Profile

- `GET /profile/summary`
- `POST /profile/facts`
- `POST /profile/preferences`
- `GET /profile/derived`
- `POST /profile/derived/refresh`
- `GET /profile/derived/latest`

## Personal Context

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

## Radar

- `POST /radar/sync`
- `POST /radar/filter`
- `POST /radar/analyze`
- `GET /radar/issues`
- `GET /radar/digest`
- `POST /radar/run`
- `POST /radar/mark-alerts`

## Ops

- `GET /ops/services`
- `POST /ops/services`
- `POST /ops/services/{service_id}/checks`
- `POST /ops/services/{service_id}/probe`
- `POST /ops/probe-all`

## Example Flow

Extract candidates from raw evidence:

```bash
curl -X POST http://127.0.0.1:5000/ingest/extract \
  -H 'content-type: application/json' \
  -d '{"source_type":"manual_text","content":"I am building ContextOS for profile-driven GitHub issue discovery."}'
```

Review pending candidates:

```bash
curl 'http://127.0.0.1:5000/ingest/candidates?status=pending'
```

Apply a confirmed candidate:

```bash
curl -X POST http://127.0.0.1:5000/ingest/candidates/1/apply
```

Run radar:

```bash
curl -X POST http://127.0.0.1:5000/radar/run \
  -H 'content-type: application/json' \
  -d '{"repo":"owner/repo","analysis_limit":5}'
```

Read digest:

```bash
curl 'http://127.0.0.1:5000/radar/digest?repo=owner/repo&lookback_days=3'
```
