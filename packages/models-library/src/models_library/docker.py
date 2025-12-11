import re
from typing import Annotated, TypeAlias

from pydantic import (
    StringConstraints,
)

from .basic_regex import DOCKER_GENERIC_TAG_KEY_RE, DOCKER_LABEL_KEY_REGEX
from .basic_types import ConstrainedStr


class DockerLabelKey(ConstrainedStr):
    # NOTE: https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
    # good practice: use reverse DNS notation
    pattern = DOCKER_LABEL_KEY_REGEX

    @classmethod
    def from_key(cls, key: str) -> "DockerLabelKey":
        return cls(key.lower().replace("_", "-"))


# NOTE: https://docs.docker.com/engine/reference/commandline/tag/#description
DockerGenericTag: TypeAlias = Annotated[
    str, StringConstraints(pattern=DOCKER_GENERIC_TAG_KEY_RE)
]

DockerPlacementConstraint: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=re.compile(
            r"^(?!-)(?![.])(?!.*--)(?!.*[.][.])[a-zA-Z0-9.-]*(?<!-)(?<![.])(!=|==)[a-zA-Z0-9_. -]*$"
        ),
    ),
]


DockerNodeID: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=re.compile(r"[a-zA-Z0-9]"))
]


# Docker placement labels for node-specific constraints
# These keys are used to identify custom placement labels that can be applied to docker nodes
# and are stripped when nodes become empty for reuse
CUSTOM_PLACEMENT_LABEL_KEYS: tuple[str, ...] = (
    "product_name",
    "user_id",
    "project_id",
    "node_id",
    "group_id",
    "wallet_id",
)
