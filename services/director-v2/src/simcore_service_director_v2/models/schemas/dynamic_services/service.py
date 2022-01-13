from enum import Enum, unique
from functools import cached_property, lru_cache, total_ordering
from pathlib import Path
from typing import Dict, Optional

from models_library.basic_types import PortInt
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import DYNAMIC_SERVICE_KEY_RE, VERSION_RE
from pydantic import BaseModel, Field

from ....meta import API_VTAG
from ..constants import UserID


@unique
class ServiceType(Enum):
    """
    Used to filter out services spawned by this service in the stack.
    The version was added to distinguish from the ones spawned by director-v0
    These values are attached to the dynamic-sidecar and its relative proxy.
    """

    MAIN = f"main-{API_VTAG}"
    DEPENDENCY = f"dependency-{API_VTAG}"


class CommonServiceDetails(BaseModel):
    key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex=DYNAMIC_SERVICE_KEY_RE,
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
        None,
        description="predefined path where the dynamic service should be served. If empty, the service shall use the root endpoint.",
        alias="service_basepath",
    )

    class Config:
        allow_population_by_field_name = True
        schema_extra = {
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
class ServiceState(Enum):
    PENDING = "pending"
    PULLING = "pulling"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            comparison_order = ServiceState.comparison_order()
            self_index = comparison_order[self]
            other_index = comparison_order[other]
            return self_index < other_index
        return NotImplemented

    @staticmethod
    @lru_cache(maxsize=2)
    def comparison_order() -> Dict["ServiceState", int]:
        """States are comparable to supportmin() on a list of ServiceState"""
        return {
            ServiceState.FAILED: 0,
            ServiceState.PENDING: 1,
            ServiceState.PULLING: 2,
            ServiceState.STARTING: 3,
            ServiceState.RUNNING: 4,
            ServiceState.COMPLETE: 5,
        }


class RunningDynamicServiceDetails(ServiceDetails):
    boot_type: ServiceBootType = Field(
        ServiceBootType.V0,
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
        None, description="the service swarm published port if any", deprecated=True
    )

    entry_point: Optional[str] = Field(
        None,
        description="if empty the service entrypoint is on the root endpoint.",
        deprecated=True,
    )
    state: ServiceState = Field(
        ..., description="service current state", alias="service_state"
    )
    message: Optional[str] = Field(
        None,
        description="additional information related to service state",
        alias="service_message",
    )

    @cached_property
    def legacy_service_url(self) -> str:
        return f"http://{self.host}:{self.internal_port}{self.basepath}"

    @classmethod
    def from_scheduler_data(
        cls,
        node_uuid: NodeID,
        scheduler_data: "SchedulerData",
        service_state: ServiceState,
        service_message: str,
    ) -> "RunningDynamicServiceDetails":
        return cls(
            boot_type=ServiceBootType.V2,
            user_id=scheduler_data.user_id,
            project_id=scheduler_data.project_id,
            node_uuid=node_uuid,
            key=scheduler_data.key,
            version=scheduler_data.version,
            host=scheduler_data.service_name,
            internal_port=scheduler_data.service_port,
            state=service_state.value,
            message=service_message,
        )

    class Config(ServiceDetails.Config):
        keep_untouched = (cached_property,)
        schema_extra = {
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
