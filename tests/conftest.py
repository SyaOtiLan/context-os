from __future__ import annotations

from pathlib import Path

import pytest
from personal_agent.config import settings
from personal_agent.db import init_db
from personal_agent.services.repository import Repository


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path) -> None:
    original_db_path = settings.db_path
    object.__setattr__(settings, "db_path", tmp_path / "test.db")
    init_db()
    try:
        yield
    finally:
        object.__setattr__(settings, "db_path", original_db_path)


@pytest.fixture
def repository() -> Repository:
    return Repository()
