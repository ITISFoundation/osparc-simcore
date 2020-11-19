# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re
import subprocess
from pathlib import Path
from typing import Dict

import pytest

# TODO: search ujson in all _base.txt and add here all services that contains it
SERVICES_WITH_EXTERNALS = "director director-v2 webserver storage catalog".split()


@pytest.mark.parametrize("service", SERVICES_WITH_EXTERNALS)
async def test_ujson_installation(
    loop,
    service: str,
    simcore_docker_compose: Dict,
    osparc_simcore_root_dir: Path,
):
    def _extract_from_dockerfile():
        dockerfile_path: Path = (
            osparc_simcore_root_dir
            / "services"
            / ("web" if service == "webserver" else service)
            / "Dockerfile"
        )

        dockerfile = dockerfile_path.read_text()
        m = re.search(r"FROM (.+) as base", dockerfile)
        assert m, f"{dockerfile_path} has no 'base' alias!?"
        return m.group(0)

    docker_base_name = _extract_from_dockerfile()
    print("Service", service, "has a base image from", docker_base_name)

    # tests failing installation undetected
    # and fixed in PR https://github.com/ITISFoundation/osparc-simcore/pull/1353
    image_name = simcore_docker_compose["services"][service]["image"]

    if "alpine" in docker_base_name:
        cmd = f"docker run -t --rm {image_name} python -c 'import ujson; print(ujson.__version__)'"
    else:
        cmd = f'docker run -t --rm {image_name} python -c "import ujson; print(ujson.__version__)"'

    print(cmd)

    assert subprocess.run(
        cmd,
        shell=True,
        check=True,
    )
