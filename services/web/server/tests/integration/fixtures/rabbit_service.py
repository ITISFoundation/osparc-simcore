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


@pytest.fixture(scope="function")
async def rabbit_service(_webserver_dev_config: Dict, docker_stack):
    cfg = deepcopy(_webserver_dev_config["rabbit"])
    host = cfg["host"]
    port = cfg["port"]
    user = cfg["user"]
    password = cfg["password"]
    url = "amqp://{}:{}@{}:{}".format(user, password, host, port)
    await wait_till_rabbit_responsive(url)

@tenacity.retry(wait=tenacity.wait_fixed(0.1), stop=tenacity.stop_after_delay(60))
async def wait_till_rabbit_responsive(url: str):
    await aio_pika.connect(url)
    return True
