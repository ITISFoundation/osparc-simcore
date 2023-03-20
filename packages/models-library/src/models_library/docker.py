import re
from typing import Optional

from models_library.generated_models.docker_rest_api import Task
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.users import UserID
from pydantic import BaseModel, ConstrainedStr, Field

from .basic_regex import DOCKER_GENERIC_TAG_KEY_RE, DOCKER_LABEL_KEY_REGEX


class DockerLabelKey(ConstrainedStr):
    # NOTE: https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
    # good practice: use reverse DNS notation
    regex: Optional[re.Pattern[str]] = DOCKER_LABEL_KEY_REGEX


class DockerGenericTag(ConstrainedStr):
    # NOTE: https://docs.docker.com/engine/reference/commandline/tag/#description
    regex: Optional[re.Pattern[str]] = DOCKER_GENERIC_TAG_KEY_RE


class SimcoreServiceDockerLabelKeys(BaseModel):
    # NOTE: in a next PR, this should be moved to packages models-library and used
    # all over, and aliases should use io.simcore.service.*
    # https://github.com/ITISFoundation/osparc-simcore/issues/3638

    user_id: UserID = Field(..., alias="user_id")
    project_id: ProjectID = Field(..., alias="study_id")
    node_id: NodeID = Field(..., alias="uuid")

    # NOTE: `simcore_user_agent` and `product_name` should become
    # mandatory once below PR reaches production
    # https://github.com/ITISFoundation/osparc-simcore/pull/3990
    product_name: Optional[ProductName] = None
    simcore_user_agent: Optional[str] = None

    def to_docker_labels(self) -> dict[str, str]:
        """returns a dictionary of strings as required by docker"""
        std_export = self.dict(by_alias=True)
        return {k: f"{v}" for k, v in std_export.items()}

    @classmethod
    def from_docker_task(cls, docker_task: Task) -> "SimcoreServiceDockerLabelKeys":
        assert docker_task.Spec  # nosec
        assert docker_task.Spec.ContainerSpec  # nosec
        task_labels = docker_task.Spec.ContainerSpec.Labels or {}
        return cls.parse_obj(task_labels)

    class Config:
        allow_population_by_field_name = True
