# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=broad-except

import re
from pathlib import Path
from typing import Pattern, Set

import pytest
from models_library.services import (
    SERVICE_KEY_RE,
    ServiceDockerData,
    ServiceKeyVersion,
    ServiceOutput,
)
from simcore_service_director_v2.modules.db.repositories.comp_tasks import (
    _get_fake_service_details,
)


@pytest.fixture(scope="session")
def frontend_client_dir(osparc_simcore_root_dir: Path) -> Path:
    frontend_client_dir = osparc_simcore_root_dir / "services" / "web" / "client"
    assert frontend_client_dir.exists()
    return frontend_client_dir


@pytest.fixture(scope="session")
def frontend_service_pattern() -> Pattern:
    frontend_service_re = r"(simcore)/(services)/(frontend)(/[\w/-]+)+"
    dummy_service = "simcore/services/frontend/file-picker"
    assert re.match(
        SERVICE_KEY_RE, dummy_service
    ), f"Service key regex changed, please change frontend_service_re accordingly: currently is {frontend_service_re} and service re is {SERVICE_KEY_RE}"
    return re.compile(frontend_service_re)


@pytest.fixture(scope="session")
def all_frontend_services(
    frontend_service_pattern: Pattern, frontend_client_dir: Path
) -> Set[str]:

    frontend_services: Set[str] = set()
    for f in frontend_client_dir.glob("**/*.js"):
        for line in f.open("r"):
            for match in re.finditer(frontend_service_pattern, line):
                frontend_services.add(match.group())

    return frontend_services


def test_only_filepicker_service_gets_some_service_details(
    all_frontend_services: Set[str],
):
    for frontend_service in all_frontend_services:
        service_key_version = ServiceKeyVersion(key=frontend_service, version="24.34.5")
        # check that it does not assert
        service_docker_data: ServiceDockerData = _get_fake_service_details(
            service_key_version
        )
        if service_docker_data:
            assert service_docker_data.key == "simcore/services/frontend/file-picker"
            assert service_docker_data.outputs["outFile"].property_type == "data:*/*"
