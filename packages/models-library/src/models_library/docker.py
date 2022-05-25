from pydantic import constr

DOCKER_IMAGE_RE = r"^([a-z0-9/\.-]+)(:[a-z0-9.]+)?"
DOCKER_IMAGE_KEY_RE = r"[a-z0-9/\.-]+"
DOCKER_IMAGE_VERSION_RE = r"[a-z0-9.]+"

DockerImage = constr(regex=DOCKER_IMAGE_RE)
DockerImageKey = constr(regex=DOCKER_IMAGE_KEY_RE)
DockerImageVersion = constr(regex=DOCKER_IMAGE_VERSION_RE)
