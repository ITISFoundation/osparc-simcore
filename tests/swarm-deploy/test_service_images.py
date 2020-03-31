# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import subprocess
from typing import Dict

import pytest
from yarl import URL


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
