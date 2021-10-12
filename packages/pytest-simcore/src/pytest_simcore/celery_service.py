# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict

import celery
import celery.bin.base
import celery.bin.celery
import celery.platforms
import pytest
from servicelib.celery_utils import CeleryRetryPolicyUponInitialization
from servicelib.tenacity_wrapper import retry

from .helpers.utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def celery_config(docker_stack: Dict, testing_environ_vars: Dict) -> Dict:
    prefix = testing_environ_vars["SWARM_STACK_NAME"]
    assert f"{prefix}_rabbit" in docker_stack["services"]

    config = {
        "host": "127.0.0.1",
        "port": get_service_published_port(
            "rabbit", testing_environ_vars["RABBIT_PORT"]
        ),
        "user": testing_environ_vars["RABBIT_USER"],
        "password": testing_environ_vars["RABBIT_PASSWORD"],
    }
    yield config


@pytest.fixture(scope="module")
def celery_service(celery_config: Dict, docker_stack: Dict) -> str:
    url = "amqp://{user}:{password}@{host}:{port}".format(**celery_config)
    wait_till_celery_responsive(url)
    yield url


@retry(**CeleryRetryPolicyUponInitialization().kwargs)
def wait_till_celery_responsive(url: str) -> None:
    app = celery.Celery("tasks", broker=url)
    status = celery.bin.celery.celery.commands["status"]()
    status.app = status.get_app()
    status.run()  # raises celery.bin.base.Error if cannot run
