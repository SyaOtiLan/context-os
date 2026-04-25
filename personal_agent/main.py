from __future__ import annotations

from fastapi import FastAPI

from personal_agent.api.artifacts import router as artifacts_router
from personal_agent.api.health import router as health_router
from personal_agent.api.ingest import router as ingest_router
from personal_agent.api.notes import router as notes_router
from personal_agent.api.overview import router as overview_router
from personal_agent.api.ops import router as ops_router
from personal_agent.api.opportunities import router as opportunities_router
from personal_agent.api.policies import router as policies_router
from personal_agent.api.profile import router as profile_router
from personal_agent.api.projects import router as projects_router
from personal_agent.api.radar import router as radar_router
from personal_agent.api.tasks import router as tasks_router
from personal_agent.config import settings
from personal_agent.db import init_db


app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(profile_router)
app.include_router(overview_router)
app.include_router(projects_router)
app.include_router(artifacts_router)
app.include_router(notes_router)
app.include_router(opportunities_router)
app.include_router(tasks_router)
app.include_router(policies_router)
app.include_router(ops_router)
app.include_router(radar_router)
