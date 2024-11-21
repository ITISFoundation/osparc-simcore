from typing import Any, Protocol, TypeAlias

from models_library.basic_types import EnvVarKey
from models_library.docker import DockerLabelKey
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_resources import BootMode
from models_library.users import UserID
from pydantic import AnyUrl, BaseModel, ConfigDict, model_validator
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

    @property
    def has_parent(self) -> bool:
        return bool(self.parent_node_id and self.parent_project_id)

    @model_validator(mode="before")
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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": 32,
                    "project_id": "ec7e595a-63ee-46a1-a04a-901b11b649f8",
                    "node_id": "39467d89-b659-4914-9359-c40b1b6d1d6d",
                    "parent_project_id": None,
                    "parent_node_id": None,
                },
                {
                    "user_id": 32,
                    "project_id": "ec7e595a-63ee-46a1-a04a-901b11b649f8",
                    "node_id": "39467d89-b659-4914-9359-c40b1b6d1d6d",
                    "parent_project_id": "887e595a-63ee-46a1-a04a-901b11b649f8",
                    "parent_node_id": "aa467d89-b659-4914-9359-c40b1b6d1d6d",
                },
            ]
        }
    )


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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "image": "ubuntu",
                    "tag": "latest",
                    "input_data": TaskInputData.model_config["json_schema_extra"]["examples"][0],  # type: ignore[index]
                    "output_data_keys": TaskOutputDataSchema.model_config["json_schema_extra"]["examples"][0],  # type: ignore[index]
                    "command": ["sleep 10", "echo hello"],
                    "envs": {"MYENV": "is an env"},
                    "labels": {"io.simcore.thelabel": "is amazing"},
                    "boot_mode": BootMode.CPU.value,
                    "task_owner": TaskOwner.model_config["json_schema_extra"]["examples"][0],  # type: ignore[index]
                },
            ]
        }
    )


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
