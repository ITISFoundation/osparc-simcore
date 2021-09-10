from .models import ContainerHostConfig, DockerContainerConfig


async def create_container_config(
    service_key: str, service_version: str, command: str
) -> DockerContainerConfig:

    return DockerContainerConfig(
        Env=[],
        Cmd=[command],
        Image=f"{service_key}:{service_version}",
        Labels={},
        HostConfig=ContainerHostConfig(Binds=[], Memory=1024 ** 3, NanoCPUs=1e9),
    )
