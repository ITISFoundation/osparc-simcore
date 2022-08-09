from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.services_resources import (
    CPU_10_PERCENT,
    CPU_100_PERCENT,
    MEMORY_50MB,
    MEMORY_250MB,
)


def spec_volume_removal_service(
    node_id: str, volume_name: str, docker_version: str
) -> AioDockerServiceSpec:
    create_service_params = {
        "name": f"dy-sidecar-volume-remover-{node_id}",
        "task_template": {
            "ContainerSpec": {
                "Command": ["docker", "volume", "rm", volume_name],
                "Image": f"docker:{docker_version}-dind",
                "Mounts": [
                    {
                        "Source": "/var/run/docker.sock",
                        "Target": "/var/run/docker.sock",
                        "Type": "bind",
                    }
                ],
            },
            "Placement": {"Constraints": [f"node.id == {node_id}"]},
            "RestartPolicy": {"Condition": "none"},
            "Resources": {
                "Reservations": {
                    "MemoryBytes": MEMORY_50MB,
                    "NanoCPUs": CPU_10_PERCENT,
                },
                "Limits": {"MemoryBytes": MEMORY_250MB, "NanoCPUs": CPU_100_PERCENT},
            },
        },
    }
    return AioDockerServiceSpec.parse_obj(create_service_params)
