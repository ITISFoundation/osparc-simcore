import logging
from typing import Final, Union

from models_library.generics import DictModel
from pydantic import (
    BaseModel,
    ByteSize,
    Field,
    StrictFloat,
    StrictInt,
    constr,
    root_validator,
)

logger = logging.getLogger(__name__)


ResourceName = str

ComposeImage = constr(regex=r"[\w/-]+:[\w.@]+")


GIGA: Final[float] = 1e9
MEMORY_50MB: Final[int] = 52_428_800
MEMORY_250MB: Final[int] = 262_144_000
CPU_10_PERCENT: Final[int] = int(0.1 * GIGA)
CPU_100_PERCENT: Final[int] = int(1 * GIGA)


class ResourceValue(BaseModel):
    limit: Union[StrictInt, StrictFloat, str]
    reservation: Union[StrictInt, StrictFloat, str]

    @root_validator()
    @classmethod
    def ensure_limits_are_equal_or_above_reservations(cls, values):
        if isinstance(values["reservation"], str):
            # in case of string, the limit is the same as the reservation
            values["limit"] = values["reservation"]
        else:
            values["limit"] = max(values["limit"], values["reservation"])

        return values


ResourcesDict = DictModel[ResourceName, ResourceValue]


class ImageResources(BaseModel):
    image: ComposeImage = Field(..., description="used by the fro")
    resources: ResourcesDict

    class Config:
        schema_extra = {
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


class ServiceResources(DictModel[str, ImageResources]):
    @classmethod
    def from_resources(cls, resource: ResourcesDict, image: str) -> "ServiceResources":
        service_resources = cls.parse_obj(
            {"container": {"image": image, "resources": resource}}
        )
        logger.debug("%s", f"{service_resources}")
        return service_resources

    class Config:
        schema_extra = {
            "examples": [
                # no compose spec (majority of services)
                {
                    "container": {
                        "image": "simcore/services/dynamic/jupyter-math:2.0.5",
                        "resources": {
                            "CPU": {"limit": 0.1, "reservation": 0.1},
                            "RAM": {
                                "limit": ByteSize(2 * 1024**3),
                                "reservation": ByteSize(2 * 1024**3),
                            },
                        },
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
                    },
                    "s4l-core": {
                        "image": "simcore/services/dynamic/s4l-core-dy:3.0.0",
                        "resources": {
                            "CPU": {"limit": 4.0, "reservation": 0.1},
                            "RAM": {"limit": 17179869184, "reservation": 536870912},
                            "VRAM": {"limit": 1, "reservation": 1},
                        },
                    },
                    "sym-server": {
                        "image": "simcore/services/dynamic/sym-server:3.0.0",
                        "resources": {
                            "CPU": {"limit": 0.1, "reservation": 0.1},
                            "RAM": {
                                "limit": ByteSize(2 * 1024**3),
                                "reservation": ByteSize(2 * 1024**3),
                            },
                        },
                    },
                },
                # compose spec with image outside the platform
                {
                    "jupyter-lab": {
                        "image": "simcore/services/dynamic/jupyter-math:4.0.0",
                        "resources": {
                            "CPU": {"limit": 0.1, "reservation": 0.1},
                            "RAM": {
                                "limit": ByteSize(2 * 1024**3),
                                "reservation": ByteSize(2 * 1024**3),
                            },
                        },
                    },
                    "proxy": {
                        "image": "traefik:v2.6.6",
                        "resources": {
                            "CPU": {"limit": 0.1, "reservation": 0.1},
                            "RAM": {
                                "limit": ByteSize(2 * 1024**3),
                                "reservation": ByteSize(2 * 1024**3),
                            },
                        },
                    },
                },
            ]
        }
