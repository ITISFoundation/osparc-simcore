from typing import Annotated, Any, TypeAlias
from uuid import uuid4

import arrow
from pydantic import GetCoreSchemaHandler, StringConstraints, ValidationInfo
from pydantic_core import CoreSchema, core_schema

from .basic_regex import PROPERTY_KEY_RE, SIMPLE_VERSION_RE
from .services_regex import (
    COMPUTATIONAL_SERVICE_KEY_RE,
    DYNAMIC_SERVICE_KEY_RE,
    FILENAME_RE,
    SERVICE_ENCODED_KEY_RE,
    SERVICE_KEY_RE,
)

ServicePortKey: TypeAlias = Annotated[str, StringConstraints(pattern=PROPERTY_KEY_RE)]

FileName: TypeAlias = Annotated[str, StringConstraints(pattern=FILENAME_RE)]

ServiceKey: TypeAlias = Annotated[str, StringConstraints(pattern=SERVICE_KEY_RE)]

ServiceKeyEncoded: TypeAlias = Annotated[
    str, StringConstraints(pattern=SERVICE_ENCODED_KEY_RE)
]

DynamicServiceKey: TypeAlias = Annotated[
    str, StringConstraints(pattern=DYNAMIC_SERVICE_KEY_RE)
]

ComputationalServiceKey: TypeAlias = Annotated[
    str, StringConstraints(pattern=COMPUTATIONAL_SERVICE_KEY_RE)
]

ServiceVersion: TypeAlias = Annotated[str, StringConstraints(pattern=SIMPLE_VERSION_RE)]


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

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,  # pylint:disable=unused-argument
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, handler(str))

    @classmethod
    def validate(cls, v: "RunID | str", _: ValidationInfo) -> "RunID":
        if isinstance(v, cls):
            return v
        if isinstance(v, str):
            return cls(v)
        msg = f"Invalid value for RunID: {v}"
        raise TypeError(msg)
