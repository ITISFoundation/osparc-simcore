from typing import Annotated

from pydantic import ByteSize, Field, TypeAdapter

from .base import BaseCustomSettings


class DynamicServicesResourceOverheadSettings(BaseCustomSettings):
    DYNAMIC_SERVICES_OVERHEAD_CPUS: Annotated[
        float,
        Field(
            ge=0,
            description=(
                "CPU cores reserved as overhead (host baseline: docker daemon + instance housekeeping, "
                "plus platform ops/monitoring). Default: 1.4 (system 1.4 + ops 0.0)"
            ),
        ),
    ] = 1.4

    DYNAMIC_SERVICES_DOCKER_NODE_AVAILABLE_RAM_RATIO: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            description=(
                "Fraction of machine RAM expected to be available to Docker on the node. "
                "This can be lower than raw machine RAM due to host/runtime overhead. Default: 0.9"
            ),
        ),
    ] = 0.9

    DYNAMIC_SERVICES_OVERHEAD_RAM_BYTES: Annotated[
        ByteSize,
        Field(
            ge=0,
            description="Absolute RAM reserved for overhead (ops/monitoring). Default: 1GiB",
        ),
    ] = TypeAdapter(ByteSize).validate_python("1GiB")
