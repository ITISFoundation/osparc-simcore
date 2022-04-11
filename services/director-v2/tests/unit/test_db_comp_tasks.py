# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=broad-except

import re
from pathlib import Path
from typing import Pattern, Set

import pytest
from models_library.services import SERVICE_KEY_RE, ServiceDockerData
from simcore_service_director_v2.modules.db.repositories.comp_tasks import (
    _FRONTEND_SERVICES_CATALOG,
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
    # FIXME: PC->SAN: this is ONLY for filepicker??
    # It should also apply for other front-end functions, right?
    # At this point, parametrized nodes are also front-end functions that
    # are evaluated at the front-end and, as the file-picker provides its output
    # when it reaches the backend.
    # SEE doc in _FRONTEND_SERVICES_CATALOG

    EXCLUDE = [
        "simcore/services/frontend/nodes-group/macros/",  # FIXME: PC->OM: This front-end service needs to be re-defined
        "simcore/services/frontend/nodes-group",
        "simcore/services/frontend/parameter/",
        "simcore/services/frontend/iterator-consumer/probe/",
    ]
    for frontend_service_key in all_frontend_services:
        if frontend_service_key in EXCLUDE:
            continue

        service_docker_data = _FRONTEND_SERVICES_CATALOG[frontend_service_key]

        assert isinstance(service_docker_data, ServiceDockerData)
        assert service_docker_data.outputs
