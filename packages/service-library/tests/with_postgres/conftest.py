# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint: disable=too-many-arguments
import sys
from pathlib import Path

import pytest
import yaml

from servicelib.aiopg_utils import DataSourceName, is_postgres_responsive

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def docker_compose_file() -> Path:
    # overrides fixture from https://github.com/AndreLouisCaron/pytest-docker
    return current_dir / "docker-compose.yml"


@pytest.fixture(scope="session")
def postgres_service(docker_services, docker_ip, docker_compose_file) -> DataSourceName:

    # container environment
    with open(docker_compose_file) as fh:
        config = yaml.safe_load(fh)
    environ = config["services"]["postgres"]["environment"]

    dsn = DataSourceName(
        user=environ["POSTGRES_USER"],
        password=environ["POSTGRES_PASSWORD"],
        host=docker_ip,
        port=docker_services.port_for("postgres", 5432),
        database=environ["POSTGRES_DB"],
        application_name="test-app",
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: is_postgres_responsive(dsn), timeout=30.0, pause=0.1,
    )
    return dsn
