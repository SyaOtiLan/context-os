from __future__ import annotations

from personal_agent import cli
from personal_agent.models import ServiceCheckCreate


def test_cli_home_command(capsys) -> None:
    exit_code = cli.main(["home"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Personal Context OS" in captured.out
    assert "Counts:" in captured.out


def test_cli_capture_and_note_list(capsys) -> None:
    assert cli.main(["capture", "remember this", "--title", "daily"]) == 0
    capture_output = capsys.readouterr().out
    assert "Captured note #" in capture_output

    assert cli.main(["note", "list"]) == 0
    list_output = capsys.readouterr().out
    assert "remember this" in list_output


def test_cli_fact_and_preference_commands(capsys) -> None:
    assert cli.main(["fact", "set", "career", "target_role", "backend", "--confidence", "0.8"]) == 0
    fact_output = capsys.readouterr().out
    assert "Saved fact career.target_role = backend" in fact_output

    assert cli.main(["preference", "add", "jobs", "backend-first", "--weight", "1.2"]) == 0
    pref_output = capsys.readouterr().out
    assert "Saved preference #" in pref_output

    assert cli.main(["fact", "list"]) == 0
    assert "target_role" in capsys.readouterr().out
    assert cli.main(["preference", "list"]) == 0
    assert "backend-first" in capsys.readouterr().out


def test_cli_project_and_artifact_commands(capsys) -> None:
    assert cli.main(["project", "add", "--slug", "myagent", "--title", "MyAgent", "--meta", "stage=mvp"]) == 0
    project_output = capsys.readouterr().out
    assert "Saved project #" in project_output

    assert cli.main(
        [
            "artifact",
            "add",
            "--project",
            "myagent",
            "--artifact-type",
            "repo",
            "--title",
            "GitHub Repo",
            "--url",
            "https://github.com/example/myagent",
        ]
    ) == 0
    artifact_output = capsys.readouterr().out
    assert "Saved artifact #" in artifact_output

    assert cli.main(["project", "list"]) == 0
    assert "myagent" in capsys.readouterr().out
    assert cli.main(["artifact", "list", "--project", "myagent"]) == 0
    assert "GitHub Repo" in capsys.readouterr().out


def test_cli_opportunity_and_task_commands(capsys) -> None:
    assert cli.main(
        [
            "opportunity",
            "add",
            "--source",
            "issueradar",
            "--kind",
            "job",
            "--title",
            "Backend Intern",
            "--tag",
            "backend",
        ]
    ) == 0
    opportunity_output = capsys.readouterr().out
    assert "Saved opportunity #" in opportunity_output

    assert cli.main(
        [
            "task",
            "add",
            "--title",
            "Evaluate and apply",
            "--status",
            "todo",
            "--priority",
            "high",
        ]
    ) == 0
    task_output = capsys.readouterr().out
    assert "Saved task #" in task_output

    assert cli.main(["opportunity", "list"]) == 0
    assert "Backend Intern" in capsys.readouterr().out
    assert cli.main(["task", "list", "--status", "todo"]) == 0
    assert "Evaluate and apply" in capsys.readouterr().out


def test_cli_policy_commands(capsys) -> None:
    assert cli.main(
        [
            "policy",
            "add",
            "--policy-type",
            "throttle",
            "--scope",
            "notifications",
            "--target",
            "issueradar",
            "--value",
            "disabled",
        ]
    ) == 0
    add_output = capsys.readouterr().out
    assert "Saved policy #" in add_output

    assert cli.main(["policy", "list"]) == 0
    list_output = capsys.readouterr().out
    assert "issueradar" in list_output


def test_cli_service_commands(monkeypatch, capsys) -> None:
    assert cli.main(
        [
            "service",
            "add",
            "--name",
            "issueradar",
            "--service-type",
            "http",
            "--endpoint",
            "https://example.com/health",
        ]
    ) == 0
    add_output = capsys.readouterr().out
    assert "Saved service #" in add_output

    def fake_build_check(self, service):
        return ServiceCheckCreate(
            status="up",
            message="HTTP 200",
            latency_ms=12,
            payload={"service_name": service.name, "http_status": 200},
        )

    monkeypatch.setattr("personal_agent.services.ops.OpsService._build_check", fake_build_check)
    assert cli.main(["service", "probe", "issueradar"]) == 0
    probe_output = capsys.readouterr().out
    assert "Probe finished for issueradar" in probe_output

    assert cli.main(["service", "list"]) == 0
    list_output = capsys.readouterr().out
    assert "issueradar" in list_output


def test_cli_invalid_datetime_returns_error(capsys) -> None:
    exit_code = cli.main(["project", "add", "--slug", "bad", "--title", "Bad", "--started-at", "not-a-date"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Invalid datetime" in captured.err


def test_cli_artifact_add_fails_for_missing_project(capsys) -> None:
    exit_code = cli.main(
        [
            "artifact",
            "add",
            "--project",
            "missing",
            "--artifact-type",
            "repo",
            "--title",
            "Ghost Repo",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Project 'missing' not found" in captured.err


def test_cli_service_probe_fails_for_missing_service(capsys) -> None:
    exit_code = cli.main(["service", "probe", "missing-service"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Service 'missing-service' not found" in captured.err


def test_cli_service_probe_all_with_no_services_prints_empty_table(capsys) -> None:
    exit_code = cli.main(["service", "probe", "--all"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "(empty)" in captured.out
