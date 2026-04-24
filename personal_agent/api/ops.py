from __future__ import annotations

from fastapi import APIRouter, HTTPException

from personal_agent.models import Service, ServiceCheck, ServiceCheckCreate, ServiceCreate
from personal_agent.services.ops import OpsService
from personal_agent.services.repository import Repository


router = APIRouter(prefix="/ops", tags=["ops"])
repository = Repository()
ops_service = OpsService(repository)


@router.get("/services", response_model=list[Service])
def list_services() -> list[Service]:
    return repository.list_services()


@router.post("/services", response_model=Service)
def create_service(payload: ServiceCreate) -> Service:
    return repository.create_service(payload)


@router.post("/services/{service_id}/checks", response_model=ServiceCheck)
def add_service_check(service_id: int, payload: ServiceCheckCreate) -> ServiceCheck:
    return repository.add_service_check(service_id, payload)


@router.post("/services/{service_id}/probe", response_model=ServiceCheck)
def probe_service(service_id: int) -> ServiceCheck:
    try:
        return ops_service.probe_service(service_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/probe-all", response_model=list[ServiceCheck])
def probe_all_services() -> list[ServiceCheck]:
    return ops_service.probe_all_services()

