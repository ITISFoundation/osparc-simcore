from enum import Enum, unique
from functools import cached_property, lru_cache, total_ordering
from pathlib import Path
from typing import Any, ClassVar

from models_library.basic_types import PortInt
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import VERSION_RE, DynamicServiceKey
from models_library.users import UserID
from pydantic import BaseModel, Field


class CommonServiceDetails(BaseModel):
    key: DynamicServiceKey = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        examples=[
            "simcore/services/dynamic/3dviewer",
        ],
        alias="service_key",
    )
    version: str = Field(
        ...,
        description="semantic version number of the node",
        regex=VERSION_RE,
        examples=["1.0.0", "0.0.1"],
        alias="service_version",
    )

    user_id: UserID
    project_id: ProjectID
    node_uuid: NodeID = Field(..., alias="service_uuid")


class ServiceDetails(CommonServiceDetails):
    basepath: Path = Field(
        default=None,
        description="predefined path where the dynamic service should be served. If empty, the service shall use the root endpoint.",
        alias="service_basepath",
    )

    class Config:
        allow_population_by_field_name = True
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "key": "simcore/services/dynamic/3dviewer",
                "version": "2.4.5",
                "user_id": 234,
                "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                "basepath": "/x/75c7f3f4-18f9-4678-8610-54a2ade78eaa",
            }
        }


@unique
class ServiceBootType(str, Enum):
    V0 = "V0"
    V2 = "V2"


@total_ordering
@unique
class ServiceState(Enum):
    PENDING = "pending"
    PULLING = "pulling"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    STOPPING = "stopping"

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            comparison_order = ServiceState.comparison_order()
            self_index = comparison_order[self]
            other_index = comparison_order[other]
            return self_index < other_index
        return NotImplemented

    @staticmethod
    @lru_cache(maxsize=2)
    def comparison_order() -> dict["ServiceState", int]:
        """States are comparable to supportmin() on a list of ServiceState"""
        return {
            ServiceState.FAILED: 0,
            ServiceState.PENDING: 1,
            ServiceState.PULLING: 2,
            ServiceState.STARTING: 3,
            ServiceState.RUNNING: 4,
            ServiceState.STOPPING: 5,
            ServiceState.COMPLETE: 6,
        }


class RunningDynamicServiceDetails(ServiceDetails):
    boot_type: ServiceBootType = Field(
        default=ServiceBootType.V0,
        description=(
            "Describes how the dynamic services was started (legacy=V0, modern=V2)."
            "Since legacy services do not have this label it defaults to V0."
        ),
    )

    host: str = Field(
        ..., description="the service swarm internal host name", alias="service_host"
    )
    internal_port: PortInt = Field(
        ..., description="the service swarm internal port", alias="service_port"
    )
    published_port: PortInt = Field(
        default=None,
        description="the service swarm published port if any",
        deprecated=True,
    )

    entry_point: str | None = Field(
        default=None,
        description="if empty the service entrypoint is on the root endpoint.",
        deprecated=True,
    )
    state: ServiceState = Field(
        ..., description="service current state", alias="service_state"
    )
    message: str | None = Field(
        default=None,
        description="additional information related to service state",
        alias="service_message",
    )

    @cached_property
    def legacy_service_url(self) -> str:
        return f"http://{self.host}:{self.internal_port}{self.basepath}"  # NOSONAR

    @classmethod
    def from_scheduler_data(
        cls,
        node_uuid: NodeID,
        scheduler_data: "SchedulerData",  # type: ignore
        service_state: ServiceState,
        service_message: str,
    ) -> "RunningDynamicServiceDetails":
        return cls.parse_obj(
            {
                "boot_type": ServiceBootType.V2,
                "user_id": scheduler_data.user_id,
                "project_id": scheduler_data.project_id,
                "service_uuid": node_uuid,
                "service_key": scheduler_data.key,
                "service_version": scheduler_data.version,
                "service_host": scheduler_data.service_name,
                "service_port": scheduler_data.service_port,
                "service_state": service_state.value,
                "service_message": service_message,
            }
        )

    class Config(ServiceDetails.Config):
        keep_untouched = (cached_property,)
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "boot_type": "V0",
                    "key": "simcore/services/dynamic/3dviewer",
                    "version": "2.4.5",
                    "user_id": 234,
                    "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    "uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "basepath": "/x/75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "host": "3dviewer_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "internal_port": 8888,
                    "state": "running",
                    "message": "",
                    "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                },
                {
                    "boot_type": "V2",
                    "key": "simcore/services/dynamic/dy-static-file-viewer-dynamic-sidecar",
                    "version": "1.0.0",
                    "user_id": 234,
                    "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    "uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "host": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "internal_port": 80,
                    "state": "running",
                    "message": "",
                    "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                },
            ]
        }
