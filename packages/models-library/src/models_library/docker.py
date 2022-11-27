import re
from typing import Optional

from pydantic import ConstrainedStr, constr

DOCKER_IMAGE_KEY_RE = r"[\w/-]+"
DOCKER_IMAGE_VERSION_RE = r"[\w/.]+"

DockerImageKey = constr(regex=DOCKER_IMAGE_KEY_RE)
DockerImageVersion = constr(regex=DOCKER_IMAGE_VERSION_RE)


class DockerLabelKey(ConstrainedStr):
    # NOTE: https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
    # good practice: use reverse DNS notation
    regex: Optional[re.Pattern[str]] = re.compile(
        r"^(?!(\.|\-|com.docker\.|io.docker\.|org.dockerproject\.))(?!.*(--|\.\.))[a-z0-9\.-]+$"
    )
