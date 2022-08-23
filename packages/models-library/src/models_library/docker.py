from pydantic import constr

DOCKER_IMAGE_KEY_RE = r"[\w/-]+"
DOCKER_IMAGE_VERSION_RE = r"[\w/.]+"

DockerImageKey = constr(regex=DOCKER_IMAGE_KEY_RE)
DockerImageVersion = constr(regex=DOCKER_IMAGE_VERSION_RE)
