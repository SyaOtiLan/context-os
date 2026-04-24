from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

import requests

from personal_agent.models import Service, ServiceCheck, ServiceCheckCreate
from personal_agent.services.repository import Repository


class OpsService:
    def __init__(self, repository: Repository | None = None) -> None:
        self.repository = repository or Repository()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                )
            }
        )

    def probe_service(self, service_id: int) -> ServiceCheck:
        service = self.repository.get_service(service_id)
        if service is None:
            raise ValueError(f"Service {service_id} not found")
        payload = self._build_check(service)
        return self.repository.add_service_check(service_id, payload)

    def probe_all_services(self) -> list[ServiceCheck]:
        checks: list[ServiceCheck] = []
        for service in self.repository.list_services():
            if not service.endpoint:
                continue
            payload = self._build_check(service)
            checks.append(self.repository.add_service_check(service.id, payload))
        return checks

    def _build_check(self, service: Service) -> ServiceCheckCreate:
        if not service.endpoint:
            raise ValueError(f"Service {service.id} does not have an endpoint configured")

        started = perf_counter()
        status = "down"
        message: str | None = None
        payload: dict[str, object] = {
            "service_name": service.name,
            "service_type": service.service_type,
            "endpoint": service.endpoint,
        }

        try:
            response = self.session.get(service.endpoint, timeout=15, allow_redirects=True)
            latency_ms = int((perf_counter() - started) * 1000)
            payload["http_status"] = response.status_code
            payload["final_url"] = str(response.url)
            if response.status_code < 400:
                status = "up"
                message = f"HTTP {response.status_code}"
            else:
                message = f"HTTP {response.status_code}"
            return ServiceCheckCreate(
                status=status,
                checked_at=datetime.now(timezone.utc),
                message=message,
                latency_ms=latency_ms,
                payload=payload,
            )
        except requests.RequestException as exc:
            latency_ms = int((perf_counter() - started) * 1000)
            payload["error"] = str(exc)
            return ServiceCheckCreate(
                status="down",
                checked_at=datetime.now(timezone.utc),
                message=str(exc),
                latency_ms=latency_ms,
                payload=payload,
            )
