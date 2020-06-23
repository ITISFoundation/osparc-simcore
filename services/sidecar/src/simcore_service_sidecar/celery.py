from .remote_debug import setup_remote_debugging
from .celery_configurator import get_rabbitmq_config_and_celery_app

setup_remote_debugging()

rabbit_config, app = get_rabbitmq_config_and_celery_app()

__all__ = ["rabbit_config", "app"]
