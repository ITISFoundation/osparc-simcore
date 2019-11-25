import io

import yaml

from simcore_service_webserver.db import (is_service_enabled,
                                          is_service_responsive)

def test_uses_same_postgres_version(docker_compose_file, osparc_simcore_root_dir):
    with io.open(docker_compose_file) as fh:
        fixture = yaml.safe_load(fh)

    with io.open(osparc_simcore_root_dir / "services" / "docker-compose.yml") as fh:
        expected = yaml.safe_load(fh)

    assert fixture['services']['postgres']['image'] == expected['services']['postgres']['image']


async def test_responsive(web_server):
    app = web_server.app
    assert is_service_enabled(app)
    assert await is_service_responsive(app)
