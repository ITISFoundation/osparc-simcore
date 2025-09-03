from celery.signals import worker_init, worker_shutdown  # type: ignore[import-untyped]
from celery_library.signals import (
    on_worker_shutdown,
)
from simcore_service_api_server.celery_worker.worker_main import (
    get_app,
    worker_init_wrapper,
)

app = get_app()

worker_init.connect(worker_init_wrapper)
worker_shutdown.connect(on_worker_shutdown)
