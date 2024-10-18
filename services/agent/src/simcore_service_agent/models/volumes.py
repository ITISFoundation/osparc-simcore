from pathlib import Path
from typing import Final

from models_library.api_schemas_directorv2.services import (
    CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import RunID
from models_library.users import UserID
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class DynamicServiceVolumeLabels(BaseModel):
    node_uuid: NodeID
    run_id: RunID
    source: str
    study_id: ProjectID
    swarm_stack_name: str
    user_id: UserID

    @property
    def directory_name(self) -> str:
        return self.source[CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME:][::-1].strip("_")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class VolumeDetails(BaseModel):
    mountpoint: Path = Field(alias="Mountpoint")
    labels: DynamicServiceVolumeLabels = Field(alias="Labels")


VolumeDetailsAdapter: Final[TypeAdapter[VolumeDetails]] = TypeAdapter(VolumeDetails)
