import pytest
from celery.contrib.testing.worker import start_worker
from celery.signals import worker_init, worker_shutdown
from simcore_service_storage.modules.celery.worker.main import (
    app,
    on_worker_init,
    on_worker_shutdown,
)

# Signals must be explicitily connected
worker_init.connect(on_worker_init)
worker_shutdown.connect(on_worker_shutdown)


@pytest.fixture
def celery_app():
    app.conf.update({"broker_url": "memory://"})
    return app


@pytest.fixture
def celery_worker(celery_app):
    with start_worker(celery_app, perform_ping_check=False) as worker:
        worker_init.send(sender=worker)
        yield worker
        worker_shutdown.send(sender=worker)
