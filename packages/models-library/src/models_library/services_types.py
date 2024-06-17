import re
from uuid import uuid4

import arrow
from pydantic import ConstrainedStr

from .basic_regex import PROPERTY_KEY_RE, VERSION_RE
from .services_regex import (
    COMPUTATIONAL_SERVICE_KEY_RE,
    DYNAMIC_SERVICE_KEY_RE,
    FILENAME_RE,
    SERVICE_ENCODED_KEY_RE,
    SERVICE_KEY_RE,
)


class ServicePortKey(ConstrainedStr):
    regex = re.compile(PROPERTY_KEY_RE)

    class Config:
        frozen = True


class FileName(ConstrainedStr):
    regex = re.compile(FILENAME_RE)

    class Config:
        frozen = True


class ServiceKey(ConstrainedStr):
    regex = SERVICE_KEY_RE

    class Config:
        frozen = True


class ServiceKeyEncoded(ConstrainedStr):
    regex = re.compile(SERVICE_ENCODED_KEY_RE)

    class Config:
        frozen = True


class DynamicServiceKey(ServiceKey):
    regex = DYNAMIC_SERVICE_KEY_RE


class ComputationalServiceKey(ServiceKey):
    regex = COMPUTATIONAL_SERVICE_KEY_RE


class ServiceVersion(ConstrainedStr):
    regex = re.compile(VERSION_RE)

    class Config:
        frozen = True


class RunID(str):
    """
    Used to assign a unique identifier to the run of a service.

    Example usage:
    The dynamic-sidecar uses this to distinguish between current
    and old volumes for different runs.
    Avoids overwriting data that left dropped on the node (due to an error)
    and gives the osparc-agent an opportunity to back it up.
    """

    __slots__ = ()

    @classmethod
    def create(cls) -> "RunID":
        # NOTE: there was a legacy version of this RunID
        # legacy version:
        #   '0ac3ed64-665b-42d2-95f7-e59e0db34242'
        # current version:
        #   '1690203099_0ac3ed64-665b-42d2-95f7-e59e0db34242'
        utc_int_timestamp: int = arrow.utcnow().int_timestamp
        run_id_format = f"{utc_int_timestamp}_{uuid4()}"
        return cls(run_id_format)
