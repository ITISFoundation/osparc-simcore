# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict

import celery
import celery.bin.base
import celery.bin.celery
import celery.platforms
import pytest
import tenacity
from servicelib.celery_utils import CeleryRetryPolicyUponInitialization
from .helpers.utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def celery_config(docker_stack: Dict, devel_environ: Dict) -> Dict:
    assert "simcore_rabbit" in docker_stack["services"]

    config = {
        "host": "127.0.0.1",
        "port": get_service_published_port("rabbit", devel_environ["RABBIT_PORT"]),
        "user": devel_environ["RABBIT_USER"],
        "password": devel_environ["RABBIT_PASSWORD"],
    }
    yield config


@pytest.fixture(scope="module")
def celery_service(celery_config: Dict, docker_stack: Dict) -> str:
    url = "amqp://{user}:{password}@{host}:{port}".format(**celery_config)
    wait_till_celery_responsive(url)
    yield url


@tenacity.retry(**CeleryRetryPolicyUponInitialization().kwargs)
def wait_till_celery_responsive(url: str) -> None:
    app = celery.Celery("tasks", broker=url)

    status = celery.bin.celery.CeleryCommand.commands["status"]()
    status.app = status.get_app()
    status.run()  # raises celery.bin.base.Error if cannot run
