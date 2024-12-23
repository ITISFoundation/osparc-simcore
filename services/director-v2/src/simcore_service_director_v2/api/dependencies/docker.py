from aiodocker import Docker
from fastapi import Request

from ...modules.docker_client import SharedDockerClient


def get_shared_docker_client(request: Request) -> Docker:
    return SharedDockerClient.docker_instance(request.app)
