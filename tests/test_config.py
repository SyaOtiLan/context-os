from __future__ import annotations

import os

from personal_agent.config import load_dotenv


def test_load_dotenv_reads_key_value_pairs(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
        # comment
        PCOS_TEST_ALPHA=one
        PCOS_TEST_BETA="two words"
        PCOS_TEST_GAMMA='three words'
        """,
        encoding="utf-8",
    )
    monkeypatch.delenv("PCOS_TEST_ALPHA", raising=False)
    monkeypatch.delenv("PCOS_TEST_BETA", raising=False)
    monkeypatch.delenv("PCOS_TEST_GAMMA", raising=False)

    load_dotenv(env_path)

    assert os.environ["PCOS_TEST_ALPHA"] == "one"
    assert os.environ["PCOS_TEST_BETA"] == "two words"
    assert os.environ["PCOS_TEST_GAMMA"] == "three words"


def test_load_dotenv_does_not_override_existing_env(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("PCOS_TEST_ALPHA=from-file", encoding="utf-8")
    monkeypatch.setenv("PCOS_TEST_ALPHA", "from-shell")

    load_dotenv(env_path)

    assert os.environ["PCOS_TEST_ALPHA"] == "from-shell"
