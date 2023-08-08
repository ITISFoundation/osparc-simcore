import logging
from enum import auto
from typing import Any, ClassVar, Final, TypeAlias

from pydantic import (
    BaseModel,
    ByteSize,
    Field,
    StrictFloat,
    StrictInt,
    parse_obj_as,
    root_validator,
)

from .docker import DockerGenericTag
from .utils.enums import StrAutoEnum
from .utils.fastapi_encoders import jsonable_encoder

_logger = logging.getLogger(__name__)


ResourceName = str

# NOTE: replace hard coded `container` with function which can
# extract the name from the `service_key` or `registry_address/service_key`
DEFAULT_SINGLE_SERVICE_NAME: Final[DockerGenericTag] = parse_obj_as(
    DockerGenericTag, "container"
)

MEMORY_50MB: Final[int] = parse_obj_as(ByteSize, "50mib")
MEMORY_250MB: Final[int] = parse_obj_as(ByteSize, "250mib")
MEMORY_1GB: Final[int] = parse_obj_as(ByteSize, "1gib")

GIGA: Final[float] = 1e9
CPU_10_PERCENT: Final[int] = int(0.1 * GIGA)
CPU_100_PERCENT: Final[int] = int(1 * GIGA)


class ResourceValue(BaseModel):
    limit: StrictInt | StrictFloat | str
    reservation: StrictInt | StrictFloat | str

    @root_validator()
    @classmethod
    def ensure_limits_are_equal_or_above_reservations(cls, values):
        if isinstance(values["reservation"], str):
            # in case of string, the limit is the same as the reservation
            values["limit"] = values["reservation"]
        elif values["limit"] <= 0:
            values["limit"] = max(values["limit"], values["reservation"])
        elif values["limit"] < values["reservation"]:
            values["reservation"] = values["limit"]

        return values

    def set_reservation_same_as_limit(self) -> None:
        self.reservation = self.limit

    class Config:
        validate_assignment = True


ResourcesDict = dict[ResourceName, ResourceValue]


class BootMode(StrAutoEnum):
    CPU = auto()
    GPU = auto()
    MPI = auto()


class ImageResources(BaseModel):
    image: DockerGenericTag = Field(
        ...,
        description=(
            "Used by the frontend to provide a context for the users."
            "Services with a docker-compose spec will have multiple entries."
            "Using the `image:version` instead of the docker-compose spec is "
            "more helpful for the end user."
        ),
    )
    resources: ResourcesDict
    boot_modes: list[BootMode] = Field(
        default=[BootMode.CPU],
        description="describe how a service shall be booted, using CPU, MPI, openMP or GPU",
    )

    def set_reservation_same_as_limit(self) -> None:
        for resource in self.resources.values():
            resource.set_reservation_same_as_limit()

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "image": "simcore/service/dynamic/pretty-intense:1.0.0",
                "resources": {
                    "CPU": {"limit": 4, "reservation": 0.1},
                    "RAM": {"limit": 103079215104, "reservation": 536870912},
                    "VRAM": {"limit": 1, "reservation": 1},
                    "AIRAM": {"limit": 1, "reservation": 1},
                    "ANY_resource": {
                        "limit": "some_value",
                        "reservation": "some_value",
                    },
                },
            }
        }


ServiceResourcesDict: TypeAlias = dict[DockerGenericTag, ImageResources]


class ServiceResourcesDictHelpers:
    @staticmethod
    def create_from_single_service(
        image: DockerGenericTag,
        resources: ResourcesDict,
        boot_modes: list[BootMode] | None = None,
    ) -> ServiceResourcesDict:
        if boot_modes is None:
            boot_modes = [BootMode.CPU]
        return parse_obj_as(
            ServiceResourcesDict,
            {
                DEFAULT_SINGLE_SERVICE_NAME: {
                    "image": image,
                    "resources": resources,
                    "boot_modes": boot_modes,
                }
            },
        )

    @staticmethod
    def create_jsonable(
        service_resources: ServiceResourcesDict,
    ) -> dict[DockerGenericTag, Any]:
        output: dict[DockerGenericTag, Any] = jsonable_encoder(service_resources)
        return output

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # no compose spec (majority of services)
                {
                    DEFAULT_SINGLE_SERVICE_NAME: {
                        "image": "simcore/services/dynamic/jupyter-math:2.0.5",
                        "resources": {
                            "CPU": {"limit": 0.1, "reservation": 0.1},
                            "RAM": {
                                "limit": parse_obj_as(ByteSize, "2Gib"),
                                "reservation": parse_obj_as(ByteSize, "2Gib"),
                            },
                        },
                        "boot_modes": [BootMode.CPU],
                    },
                },
                # service with a compose spec
                {
                    "rt-web-dy": {
                        "image": "simcore/services/dynamic/sim4life-dy:3.0.0",
                        "resources": {
                            "CPU": {"limit": 0.3, "reservation": 0.3},
                            "RAM": {"limit": 53687091232, "reservation": 53687091232},
                        },
                        "boot_modes": [BootMode.CPU],
                    },
                    "s4l-core": {
                        "image": "simcore/services/dynamic/s4l-core-dy:3.0.0",
                        "resources": {
                            "CPU": {"limit": 4.0, "reservation": 0.1},
                            "RAM": {"limit": 17179869184, "reservation": 536870912},
                            "VRAM": {"limit": 1, "reservation": 1},
                        },
                        "boot_modes": [BootMode.GPU],
                    },
                    "sym-server": {
                        "image": "simcore/services/dynamic/sym-server:3.0.0",
                        "resources": {
                            "CPU": {"limit": 0.1, "reservation": 0.1},
                            "RAM": {
                                "limit": parse_obj_as(ByteSize, "2Gib"),
                                "reservation": parse_obj_as(ByteSize, "2Gib"),
                            },
                        },
                        "boot_modes": [BootMode.CPU],
                    },
                },
                # compose spec with image outside the platform
                {
                    "jupyter-lab": {
                        "image": "simcore/services/dynamic/jupyter-math:4.0.0",
                        "resources": {
                            "CPU": {"limit": 0.1, "reservation": 0.1},
                            "RAM": {
                                "limit": parse_obj_as(ByteSize, "2Gib"),
                                "reservation": parse_obj_as(ByteSize, "2Gib"),
                            },
                        },
                        "boot_modes": [BootMode.CPU],
                    },
                    "proxy": {
                        "image": "traefik:v2.6.6",
                        "resources": {
                            "CPU": {"limit": 0.1, "reservation": 0.1},
                            "RAM": {
                                "limit": parse_obj_as(ByteSize, "2Gib"),
                                "reservation": parse_obj_as(ByteSize, "2Gib"),
                            },
                        },
                        "boot_modes": [BootMode.CPU],
                    },
                },
            ]
        }
