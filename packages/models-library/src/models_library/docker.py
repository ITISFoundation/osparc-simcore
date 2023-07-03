import re
from typing import Final

from models_library.generated_models.docker_rest_api import Task
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.users import UserID
from pydantic import BaseModel, ByteSize, ConstrainedStr, Field

from .basic_regex import DOCKER_GENERIC_TAG_KEY_RE, DOCKER_LABEL_KEY_REGEX


class DockerLabelKey(ConstrainedStr):
    # NOTE: https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
    # good practice: use reverse DNS notation
    regex: re.Pattern[str] | None = DOCKER_LABEL_KEY_REGEX


class DockerGenericTag(ConstrainedStr):
    # NOTE: https://docs.docker.com/engine/reference/commandline/tag/#description
    regex: re.Pattern[str] | None = DOCKER_GENERIC_TAG_KEY_RE


_SIMCORE_CONTAINER_PREFIX: Final[str] = "io.simcore.container."


class SimcoreServiceDockerLabelKeys(BaseModel):
    # NOTE: in a next PR, this should be moved to packages models-library and used
    # all over, and aliases should use io.simcore.service.*
    # https://github.com/ITISFoundation/osparc-simcore/issues/3638

    # The alias is for backwards compatibility, can be removed in a few sprints
    user_id: UserID = Field(..., alias="user_id")
    project_id: ProjectID = Field(..., alias="study_id")
    node_id: NodeID = Field(..., alias="uuid")

    product_name: ProductName = "osparc"
    simcore_user_agent: str = "undefined"

    # None is for backwards compatibility, can be removed in a few sprints
    memory_limit: ByteSize | None
    cpu_limit: float | None

    def to_docker_labels(self) -> dict[DockerLabelKey, str]:
        """returns a dictionary of strings as required by docker"""
        std_export = self.dict(by_alias=True)
        return {
            DockerLabelKey(f"{_SIMCORE_CONTAINER_PREFIX}{k.replace('_', '-')}"): f"{v}"
            for k, v in sorted(std_export.items())
        }

    @classmethod
    def from_docker_task(cls, docker_task: Task) -> "SimcoreServiceDockerLabelKeys":
        assert docker_task.Spec  # nosec
        assert docker_task.Spec.ContainerSpec  # nosec
        task_labels = docker_task.Spec.ContainerSpec.Labels or {}
        return cls.parse_obj(task_labels)

    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "examples": [
                # legacy with no limits (a.k.a all dynamic services)
                {
                    "uuid": "1f963626-66e1-43f1-a777-33955c08b909",
                    "study_id": "29f393fc-1410-47b3-b4b9-61dfce21a2a6",
                    "user_id": "5",
                    "product_name": "osparc",
                    "simcore_user_agent": "puppeteer",
                },
                # modern both dynamic-sidecar services and computational services
                {
                    "io.simcore.container.node-id": "1f963626-66e1-43f1-a777-33955c08b909",
                    "io.simcore.container.project-id": "29f393fc-1410-47b3-b4b9-61dfce21a2a6",
                    "io.simcore.container.user-id": "5",
                    "io.simcore.container.product-name": "osparc",
                    "io.simcore.container.simcore-user-agent": "puppeteer",
                    "io.simcore.container.memory-limit": "1073741824",
                    "io.simcore.container.cpu-limit": "2.4",
                },
            ]
        }
