# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import celery
import celery.bin.base
import celery.bin.celery
import celery.platforms
import pytest
import tenacity


@pytest.fixture(scope="module")
def celery_service(app_config, docker_stack):
    cfg = app_config["rabbit"]
    host = cfg["host"]
    port = cfg["port"]
    user = cfg["user"]
    password = cfg["password"]
    url = "amqp://{}:{}@{}:{}".format(user, password, host, port)
    wait_till_celery_responsive(url)
    yield url

@tenacity.retry(wait=tenacity.wait_fixed(0.1), stop=tenacity.stop_after_delay(60))
def wait_till_celery_responsive(url):
    app = celery.Celery('tasks', broker=url)

    status = celery.bin.celery.CeleryCommand.commands['status']()
    status.app = status.get_app()
    status.run()
