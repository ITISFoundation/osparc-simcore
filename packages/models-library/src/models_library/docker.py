import contextlib
import re
from typing import Any, ClassVar, Final

from models_library.generated_models.docker_rest_api import Task
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import (
    BaseModel,
    ByteSize,
    ConstrainedStr,
    Field,
    ValidationError,
    parse_obj_as,
    root_validator,
)

from .basic_regex import DOCKER_GENERIC_TAG_KEY_RE, DOCKER_LABEL_KEY_REGEX


class DockerLabelKey(ConstrainedStr):
    # NOTE: https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
    # good practice: use reverse DNS notation
    regex: re.Pattern[str] | None = DOCKER_LABEL_KEY_REGEX


class DockerGenericTag(ConstrainedStr):
    # NOTE: https://docs.docker.com/engine/reference/commandline/tag/#description
    regex: re.Pattern[str] | None = DOCKER_GENERIC_TAG_KEY_RE


_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX: Final[str] = "io.simcore.runtime."
_BACKWARDS_COMPATIBILITY_SIMCORE_RUNTIME_DOCKER_LABELS_MAP: Final[dict[str, str]] = {
    "node_id": f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}node-id",
    "product_name": f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}product-name",
    "project_id": f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}project-id",
    "simcore_user_agent": f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}simcore-user-agent",
    "study_id": f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}project-id",
    "user_id": f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}user-id",
    "uuid": f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}node-id",
    "mem_limit": f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}memory-limit",
    "swarm_stack_name": f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}swarm-stack-name",
}
_UNDEFINED_LABEL_VALUE_STR: Final[str] = "undefined"
_UNDEFINED_LABEL_VALUE_INT: Final[str] = "0"


def to_simcore_runtime_docker_label_key(key: str) -> DockerLabelKey:
    return DockerLabelKey(
        f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}{key.replace('_', '-').lower()}"
    )


class StandardSimcoreDockerLabels(BaseModel):
    """
    Represents the standard label on oSparc created containers (not yet services)
    In order to create this object in code, please use construct() method!
    """

    user_id: UserID = Field(..., alias=f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}user-id")
    project_id: ProjectID = Field(
        ..., alias=f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}project-id"
    )
    node_id: NodeID = Field(..., alias=f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}node-id")

    product_name: ProductName = Field(
        ..., alias=f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}product-name"
    )
    simcore_user_agent: str = Field(
        ..., alias=f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}simcore-user-agent"
    )

    swarm_stack_name: str = Field(
        ..., alias=f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}swarm-stack-name"
    )

    memory_limit: ByteSize = Field(
        ..., alias=f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}memory-limit"
    )
    cpu_limit: float = Field(
        ..., alias=f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}cpu-limit"
    )

    @root_validator(pre=True)
    @classmethod
    def _backwards_compatibility(cls, values: dict[str, Any]) -> dict[str, Any]:
        # NOTE: this is necessary for dy-sidecar and legacy service until they are adjusted
        if mapped_values := {
            _BACKWARDS_COMPATIBILITY_SIMCORE_RUNTIME_DOCKER_LABELS_MAP[k]: v
            for k, v in values.items()
            if k in _BACKWARDS_COMPATIBILITY_SIMCORE_RUNTIME_DOCKER_LABELS_MAP
        }:
            # these values were sometimes omitted, so let's provide some defaults
            for key in ["product-name", "simcore-user-agent", "swarm-stack-name"]:
                mapped_values.setdefault(
                    f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}{key}",
                    _UNDEFINED_LABEL_VALUE_STR,
                )

            mapped_values.setdefault(
                f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}memory-limit",
                _UNDEFINED_LABEL_VALUE_INT,
            )

            def _convert_nano_cpus_to_cpus(nano_cpu: str) -> str:
                with contextlib.suppress(ValidationError):
                    return f"{parse_obj_as(float, nano_cpu) / (1.0*10**9):.2f}"
                return _UNDEFINED_LABEL_VALUE_INT

            mapped_values.setdefault(
                f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}cpu-limit",
                _convert_nano_cpus_to_cpus(
                    values.get("nano_cpus_limit", _UNDEFINED_LABEL_VALUE_INT)
                ),
            )
            return mapped_values
        return values

    def to_simcore_runtime_docker_labels(self) -> dict[DockerLabelKey, str]:
        """returns a dictionary of strings as required by docker"""
        return {
            to_simcore_runtime_docker_label_key(k): f"{v}"
            for k, v in sorted(self.dict().items())
        }

    @classmethod
    def from_docker_task(cls, docker_task: Task) -> "StandardSimcoreDockerLabels":
        assert docker_task.Spec  # nosec
        assert docker_task.Spec.ContainerSpec  # nosec
        task_labels = docker_task.Spec.ContainerSpec.Labels or {}
        return cls.parse_obj(task_labels)

    class Config:
        allow_population_by_field_name = True
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # legacy service labels
                {
                    "study_id": "29f393fc-1410-47b3-b4b9-61dfce21a2a6",
                    "swarm_stack_name": "devel-simcore",
                    "user_id": "5",
                    "uuid": "1f963626-66e1-43f1-a777-33955c08b909",
                },
                # legacy container labels
                {
                    "mem_limit": "1073741824",
                    "nano_cpus_limit": "4000000000",
                    "node_id": "1f963626-66e1-43f1-a777-33955c08b909",
                    "simcore_user_agent": "puppeteer",
                    "study_id": "29f393fc-1410-47b3-b4b9-61dfce21a2a6",
                    "swarm_stack_name": "devel-simcore",
                    "user_id": "5",
                },
                # dy-sidecar service labels
                {
                    "study_id": "29f393fc-1410-47b3-b4b9-61dfce21a2a6",
                    "swarm_stack_name": "devel-simcore",
                    "user_id": "5",
                    "uuid": "1f963626-66e1-43f1-a777-33955c08b909",
                },
                # dy-sidecar container labels
                {
                    "mem_limit": "1073741824",
                    "nano_cpus_limit": "4000000000",
                    "study_id": "29f393fc-1410-47b3-b4b9-61dfce21a2a6",
                    "user_id": "5",
                    "uuid": "1f963626-66e1-43f1-a777-33955c08b909",
                },
                # dy-proxy service labels
                {
                    "dynamic-type": "dynamic-sidecar",
                    "study_id": "29f393fc-1410-47b3-b4b9-61dfce21a2a6",
                    "swarm_stack_name": "devel-simcore",
                    "type": "dependency-v2",
                    "user_id": "5",
                    "uuid": "1f963626-66e1-43f1-a777-33955c08b909",
                },
                # dy-proxy container labels
                {
                    "study_id": "29f393fc-1410-47b3-b4b9-61dfce21a2a6",
                    "user_id": "5",
                    "uuid": "1f963626-66e1-43f1-a777-33955c08b909",
                },
                # dy-sidecar user-services labels
                {
                    "product_name": "osparc",
                    "simcore_user_agent": "puppeteer",
                    "study_id": "29f393fc-1410-47b3-b4b9-61dfce21a2a6",
                    "user_id": "5",
                    "uuid": "1f963626-66e1-43f1-a777-33955c08b909",
                },
                # modern both dynamic-sidecar services and computational services
                {
                    "io.simcore.runtime.cpu-limit": "2.4",
                    "io.simcore.runtime.memory-limit": "1073741824",
                    "io.simcore.runtime.node-id": "1f963626-66e1-43f1-a777-33955c08b909",
                    "io.simcore.runtime.product-name": "osparc",
                    "io.simcore.runtime.project-id": "29f393fc-1410-47b3-b4b9-61dfce21a2a6",
                    "io.simcore.runtime.simcore-user-agent": "puppeteer",
                    "io.simcore.runtime.swarm-stack-name": "devel-osparc",
                    "io.simcore.runtime.user-id": "5",
                },
            ]
        }
