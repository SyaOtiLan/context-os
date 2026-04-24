from __future__ import annotations

from types import SimpleNamespace

import pytest
import requests

from personal_agent.models import ServiceCreate
from personal_agent.services.ops import OpsService


def test_probe_service_success_records_up_status(repository) -> None:
    service = repository.create_service(
        ServiceCreate(
            name="issueradar",
            service_type="http",
            endpoint="https://example.com/health",
        )
    )
    ops = OpsService(repository)

    def fake_get(url: str, timeout: int, allow_redirects: bool) -> SimpleNamespace:
        assert url == "https://example.com/health"
        assert timeout == 15
        assert allow_redirects is True
        return SimpleNamespace(status_code=200, url=url)

    ops.session.get = fake_get  # type: ignore[method-assign]

    check = ops.probe_service(service.id)

    refreshed_service = repository.get_service(service.id)
    assert check.status == "up"
    assert check.message == "HTTP 200"
    assert check.payload["http_status"] == 200
    assert refreshed_service is not None
    assert refreshed_service.status == "up"


def test_probe_service_failure_records_down_status(repository) -> None:
    service = repository.create_service(
        ServiceCreate(
            name="issueradar",
            service_type="http",
            endpoint="https://example.com/health",
        )
    )
    ops = OpsService(repository)

    def fake_get(url: str, timeout: int, allow_redirects: bool) -> SimpleNamespace:
        raise requests.RequestException("network down")

    ops.session.get = fake_get  # type: ignore[method-assign]

    check = ops.probe_service(service.id)

    assert check.status == "down"
    assert check.message == "network down"
    assert check.payload["error"] == "network down"


def test_probe_all_services_skips_services_without_endpoint(repository) -> None:
    repository.create_service(ServiceCreate(name="with-endpoint", service_type="http", endpoint="https://example.com/health"))
    repository.create_service(ServiceCreate(name="no-endpoint", service_type="worker"))
    ops = OpsService(repository)

    def fake_get(url: str, timeout: int, allow_redirects: bool) -> SimpleNamespace:
        return SimpleNamespace(status_code=204, url=url)

    ops.session.get = fake_get  # type: ignore[method-assign]

    checks = ops.probe_all_services()

    assert len(checks) == 1
    assert checks[0].payload["service_name"] == "with-endpoint"
