from enum import auto

from models_library.utils.enums import StrAutoEnum


class BootServerMode(StrAutoEnum):
    AS_REST = auto()
    AS_CELERY_WORKER = auto()
