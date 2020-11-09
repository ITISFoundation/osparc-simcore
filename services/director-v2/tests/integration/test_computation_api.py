# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from typing import Dict

import pytest
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from starlette.testclient import TestClient
from yarl import URL

core_services = ["director", "redis", "rabbit", "sidecar", "postgres"]
ops_services = ["minio"]


@pytest.fixture(autouse=True)
def minimal_configuration(
    sleeper_service: Dict[str, str],
    redis_service: RedisConfig,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitConfig,
    simcore_services: Dict[str, URL],
    monkeypatch,
):
    pass


def test_start_computation(client: TestClient):
    import pdb

    pdb.set_trace()


def test_abort_computation():
    pass
