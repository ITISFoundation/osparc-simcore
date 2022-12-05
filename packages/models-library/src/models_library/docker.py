import re
from typing import Final, Optional

from pydantic import ConstrainedStr, constr

_DOCKER_LABEL_KEY_REGEX: Final[re.Pattern] = re.compile(
    r"^(?!(\.|\-|com.docker\.|io.docker\.|org.dockerproject\.))(?!.*(--|\.\.))[a-z0-9\.-]+$"
)
DOCKER_IMAGE_KEY_RE = r"[\w/-]+"
DOCKER_IMAGE_VERSION_RE = r"[\w/.]+"

DockerImageKey = constr(regex=DOCKER_IMAGE_KEY_RE)
DockerImageVersion = constr(regex=DOCKER_IMAGE_VERSION_RE)


class DockerLabelKey(ConstrainedStr):
    # NOTE: https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
    # good practice: use reverse DNS notation
    regex: Optional[re.Pattern[str]] = _DOCKER_LABEL_KEY_REGEX
