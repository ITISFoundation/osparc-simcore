from enum import StrEnum


class CeleryPoolType(StrEnum):
    PREFORK = "prefork"
    EVENTLET = "eventlet"
    GEVENT = "gevent"
    SOLO = "solo"
    THREADS = "threads"
