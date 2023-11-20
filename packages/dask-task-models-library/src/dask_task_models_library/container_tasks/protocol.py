from typing import Any, Protocol, TypeAlias

from models_library.basic_types import EnvVarKey
from models_library.docker import DockerLabelKey
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_resources import BootMode
from models_library.users import UserID
from pydantic import AnyUrl, BaseModel, root_validator
from settings_library.s3 import S3Settings

from .docker import DockerBasicAuth
from .io import TaskInputData, TaskOutputData, TaskOutputDataSchema

ContainerImage: TypeAlias = str
ContainerTag: TypeAlias = str
LogFileUploadURL: TypeAlias = AnyUrl
ContainerCommands: TypeAlias = list[str]
ContainerEnvsDict: TypeAlias = dict[EnvVarKey, str]
ContainerLabelsDict: TypeAlias = dict[DockerLabelKey, str]


class TaskOwner(BaseModel):
    user_id: UserID
    project_id: ProjectID
    node_id: NodeID

    parent_project_id: ProjectID | None
    parent_node_id: NodeID | None

    @root_validator
    @classmethod
    def check_parent_valid(cls, values: dict[str, Any]) -> dict[str, Any]:
        parent_project_id = values.get("parent_project_id")
        parent_node_id = values.get("parent_node_id")
        if (parent_node_id is None and parent_project_id is not None) or (
            parent_node_id is not None and parent_project_id is None
        ):
            msg = "either both parent_node_id and parent_project_id are None or both are set!"
            raise ValueError(msg)
        return values


class ContainerTaskParameters(BaseModel):
    image: ContainerImage
    tag: ContainerTag
    input_data: TaskInputData
    output_data_keys: TaskOutputDataSchema
    command: ContainerCommands
    envs: ContainerEnvsDict
    labels: ContainerLabelsDict
    boot_mode: BootMode
    task_owner: TaskOwner


class ContainerRemoteFct(Protocol):
    def __call__(
        self,
        *,
        task_parameters: ContainerTaskParameters,
        docker_auth: DockerBasicAuth,
        log_file_url: LogFileUploadURL,
        s3_settings: S3Settings | None,
    ) -> TaskOutputData:
        ...
