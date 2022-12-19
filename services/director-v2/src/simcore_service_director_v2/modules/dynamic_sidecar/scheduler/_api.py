from ._core._events_utils import (
    service_push_outputs,
    service_remove_containers,
    service_remove_sidecar_proxy_docker_networks_and_volumes,
    service_save_state,
)

# avoids exposing the internals
push_outputs = service_push_outputs
remove_containers = service_remove_containers
remove_sidecar_proxy_docker_networks_and_volumes = (
    service_remove_sidecar_proxy_docker_networks_and_volumes
)
save_state = service_save_state

__all__: tuple[str, ...] = (
    "push_outputs",
    "remove_containers",
    "remove_sidecar_proxy_docker_networks_and_volumes",
    "save_state",
)
