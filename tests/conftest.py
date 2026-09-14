"""Shared fixtures. One service and one analysis are reused across the suite -
bootstrapping loads 956 records and 33 skill definitions, which is fast but not
free."""
from __future__ import annotations

import pytest

from appliance.service import ApplianceService

REFERENCE_SCENARIO = "SCN-001"


@pytest.fixture(scope="session")
def service() -> ApplianceService:
    return ApplianceService()


@pytest.fixture(scope="session")
def analysis(service) -> dict:
    return service.analyse_scenario(REFERENCE_SCENARIO)


@pytest.fixture(scope="session")
def context(analysis):
    return analysis["context"]
