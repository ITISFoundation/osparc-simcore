# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from copy import deepcopy
from typing import Dict

import aio_pika
import pytest
import tenacity

from utils_docker import get_service_published_port

@pytest.fixture(scope="module")
def rabbit_config(docker_stack: Dict, devel_environ: Dict) -> Dict:
    assert "simcore_rabbit" in docker_stack["services"]

    config = {
        "host": "127.0.0.1",
        "port": get_service_published_port("rabbit", devel_environ["RABBIT_PORT"]),
        "user": devel_environ["RABBIT_USER"],
        "password": devel_environ["RABBIT_PASSWORD"],
    }
    yield config

@pytest.fixture(scope="function")
async def rabbit_service(rabbit_config: Dict, docker_stack: Dict) -> str:
    url = "amqp://{user}:{password}@{host}:{port}".format(**rabbit_config)
    await wait_till_rabbit_responsive(url)
    yield url


@tenacity.retry(wait=tenacity.wait_fixed(0.1), stop=tenacity.stop_after_delay(60))
async def wait_till_rabbit_responsive(url: str):
    await aio_pika.connect(url)
    return True
