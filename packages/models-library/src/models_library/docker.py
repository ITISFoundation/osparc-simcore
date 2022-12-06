import re
from typing import Optional

from pydantic import ConstrainedStr, constr

from .basic_regex import (
    DOCKER_IMAGE_KEY_RE,
    DOCKER_IMAGE_VERSION_RE,
    DOCKER_LABEL_KEY_REGEX,
)

DockerImageKey = constr(regex=DOCKER_IMAGE_KEY_RE)
DockerImageVersion = constr(regex=DOCKER_IMAGE_VERSION_RE)


class DockerLabelKey(ConstrainedStr):
    # NOTE: https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
    # good practice: use reverse DNS notation
    regex: Optional[re.Pattern[str]] = DOCKER_LABEL_KEY_REGEX
