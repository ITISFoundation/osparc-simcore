# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "package_name,services",
    [
        ("magic", {"webserver"}),
    ],
)
async def test_python_package_installation(
    package_name: str,
    services: set[str],
    simcore_docker_compose: dict,
    osparc_simcore_root_dir: Path,
):
    def _extract_from_dockerfile(service_name: str) -> str:
        dockerfile_path: Path = (
            osparc_simcore_root_dir
            / "services"
            / ("web" if service_name == "webserver" else service_name)
            / "Dockerfile"
        )

        dockerfile = dockerfile_path.read_text()
        m = re.search(r"FROM (.+) AS base", dockerfile)
        assert m, f"{dockerfile_path} has no 'base' alias!?"
        return m.group(0)

    for service in services:
        docker_base_name = _extract_from_dockerfile(service)
        print("Service", service, "has a base image from", docker_base_name)

        # tests failing installation undetected
        # and fixed in PR https://github.com/ITISFoundation/osparc-simcore/pull/1353
        image_name = simcore_docker_compose["services"][service]["image"]

        if "alpine" in docker_base_name:
            cmd = f"docker run -t --rm {image_name} python -c 'import {package_name}'"
        else:
            cmd = f'docker run -t --rm {image_name} python -c "import {package_name}"'

        print(cmd)

        assert subprocess.run(
            cmd,
            shell=True,
            check=True,
        )
