from celery import Celery

from simcore_sdk.config.rabbit import Config as rabbit_config

rc = rabbit_config()
celery = Celery(rc.name, broker=rc.broker, backend=rc.backend)
