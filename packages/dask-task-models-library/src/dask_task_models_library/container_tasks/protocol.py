from typing import Protocol, TypeAlias

from models_library.basic_types import EnvVarKey
from models_library.docker import DockerLabelKey
from models_library.services_resources import BootMode
from pydantic import AnyUrl
from settings_library.s3 import S3Settings

from .docker import DockerBasicAuth
from .io import TaskInputData, TaskOutputData, TaskOutputDataSchema

ContainerImage: TypeAlias = str
ContainerTag: TypeAlias = str
LogFileUploadURL: TypeAlias = AnyUrl
ContainerCommands: TypeAlias = list[str]
ContainerEnvsDict: TypeAlias = dict[EnvVarKey, str]
ContainerLabelsDict: TypeAlias = dict[DockerLabelKey, str]


class ContainerRemoteFct(Protocol):
    def __call__(  # noqa: PLR0913
        self,
        *,
        docker_auth: DockerBasicAuth,
        service_key: ContainerImage,
        service_version: ContainerTag,
        input_data: TaskInputData,
        output_data_keys: TaskOutputDataSchema,
        log_file_url: LogFileUploadURL,
        command: ContainerCommands,
        task_envs: ContainerEnvsDict,
        task_labels: ContainerLabelsDict,
        s3_settings: S3Settings | None,
        boot_mode: BootMode,
    ) -> TaskOutputData:
        ...
