from typing import Annotated

from pydantic import ByteSize, Field, TypeAdapter

from .base import BaseCustomSettings


class DynamicServicesResourceOverheadSettings(BaseCustomSettings):
    DYNAMIC_SERVICES_SYSTEM_OVERHEAD_CPUS: Annotated[
        float,
        Field(
            ge=0,
            description=("CPU cores reserved as host baseline overhead (docker daemon + instance housekeeping)"),
        ),
    ] = 1.4

    DYNAMIC_SERVICES_OPS_OVERHEAD_CPUS: Annotated[
        float,
        Field(
            ge=0,
            description="CPU cores reserved for platform ops/monitoring overhead",
        ),
    ] = 0.0

    DYNAMIC_SERVICES_DOCKER_NODE_AVAILABLE_RAM_RATIO: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            description=(
                "Fraction of machine RAM expected to be available to Docker on the node. "
                "This can be lower than raw machine RAM due to host/runtime overhead"
            ),
        ),
    ] = 0.9

    DYNAMIC_SERVICES_OPS_OVERHEAD_RAM_BYTES: Annotated[
        ByteSize,
        Field(
            ge=0,
            description="Absolute RAM reserved for ops/monitoring overhead",
        ),
    ] = TypeAdapter(ByteSize).validate_python("1GiB")
