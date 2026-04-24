from __future__ import annotations

from fastapi import APIRouter

from personal_agent.models import (
    DerivedProfile,
    DerivedProfileSnapshot,
    ProfileFact,
    ProfileFactCreate,
    ProfilePreference,
    ProfilePreferenceCreate,
    ProfileSummary,
)
from personal_agent.services.profile_derivation import ProfileDerivationService
from personal_agent.services.repository import Repository


router = APIRouter(prefix="/profile", tags=["profile"])
repository = Repository()
derivation_service = ProfileDerivationService(repository)


@router.get("/summary", response_model=ProfileSummary)
def summary() -> ProfileSummary:
    return ProfileSummary(
        facts=repository.list_profile_facts(),
        preferences=repository.list_profile_preferences(),
    )


@router.get("/derived", response_model=DerivedProfile)
def derived_profile() -> DerivedProfile:
    return derivation_service.build_profile()


@router.get("/derived/latest", response_model=DerivedProfileSnapshot | None)
def latest_derived_profile() -> DerivedProfileSnapshot | None:
    return repository.get_latest_profile_snapshot()


@router.post("/derived/refresh", response_model=DerivedProfileSnapshot)
def refresh_derived_profile() -> DerivedProfileSnapshot:
    return derivation_service.build_and_store_profile()


@router.post("/facts", response_model=ProfileFact)
def upsert_fact(payload: ProfileFactCreate) -> ProfileFact:
    return repository.upsert_profile_fact(payload)


@router.post("/preferences", response_model=ProfilePreference)
def add_preference(payload: ProfilePreferenceCreate) -> ProfilePreference:
    return repository.add_profile_preference(payload)
