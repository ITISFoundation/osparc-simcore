# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import subprocess
from typing import Dict

import pytest
from yarl import URL

core_services = []

ops_services = []


@pytest.fixture(scope="module")
def all_services(
    simcore_docker_compose: Dict, ops_docker_compose: Dict, request
) -> Dict:
    services = []
    for service in simcore_docker_compose["services"].keys():
        services.append(service)
    setattr(request.module, "core_services", services)
    core_services = getattr(request.module, "core_services", [])

    services = []
    for service in ops_docker_compose["services"].keys():
        services.append(service)
    setattr(request.module, "ops_services", services)
    ops_services = getattr(request.module, "ops_services", [])

    services = {"simcore": simcore_docker_compose, "ops": ops_docker_compose}
    return services


# search ujson in all _base.txt and add here all services that contains it
@pytest.mark.parametrize(
    "service,type",
    [
        ("director", "debian"),
        ("webserver", "alpine"),
        ("storage", "alpine"),
        ("catalog", "alpine"),
    ],
)
async def test_ujson_installation(
    loop, service: str, type: str, simcore_docker_compose: Dict,
):
    # tets failing installation undetected
    # and fixed in PR https://github.com/ITISFoundation/osparc-simcore/pull/1353
    image_name = simcore_docker_compose["services"][service]["image"]

    if type == "debian":
        assert subprocess.run(
            f"docker run -t --rm {image_name} \"python -c 'import ujson; print(ujson.__version__)'\"",
            shell=True,
            check=True,
        )
    else:
        assert subprocess.run(
            f"docker run -t --rm {image_name} python -c 'import ujson; print(ujson.__version__)'",
            shell=True,
            check=True,
        )
