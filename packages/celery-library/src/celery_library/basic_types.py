from enum import auto

from models_library.utils.enums import StrAutoEnum


class BootServerMode(StrAutoEnum):
    """Defines how the service boots and runs.

    Different boot modes allow services to run either as REST servers or as Celery workers,
    enabling flexible deployment strategies and execution contexts.
    """

    AS_REST_API_SERVER = auto()
    AS_CELERY_WORKER = auto()
