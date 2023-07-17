# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from pathlib import Path

import yaml
from aiohttp.test_utils import TestServer
from simcore_service_webserver.db.plugin import (
    is_service_enabled,
    is_service_responsive,
)


def test_uses_same_postgres_version(
    docker_compose_file: Path, osparc_simcore_root_dir: Path
):
    with open(docker_compose_file) as fh:
        fixture = yaml.safe_load(fh)

    with open(osparc_simcore_root_dir / "services" / "docker-compose.yml") as fh:
        expected = yaml.safe_load(fh)

    assert (
        fixture["services"]["postgres"]["image"]
        == expected["services"]["postgres"]["image"]
    )


async def test_responsive(web_server: TestServer):
    app = web_server.app
    assert is_service_enabled(app)
    assert await is_service_responsive(app)
