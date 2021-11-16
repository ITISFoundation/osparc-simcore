from typing import Any, Dict

from pydantic.types import PositiveInt

from ....core.settings import DynamicSidecarProxySettings, DynamicSidecarSettings
from ....models.schemas.dynamic_services import SchedulerData, ServiceType

MEMORY_50MB = 52430000
CPU_1_PERCENT = 10000000


def get_dynamic_proxy_spec(
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    swarm_network_name: str,
    dynamic_sidecar_node_id: str,
    entrypoint_container_name: str,
    service_port: PositiveInt,
) -> Dict[str, Any]:
    """
    The Traefik proxy is the entrypoint which forwards
    all the network requests to dynamic service.
    The proxy is used to create network isolation
    from the rest of the platform.
    """

    mounts = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
            "ReadOnly": True,
        }
    ]
    proxy_settings: DynamicSidecarProxySettings = (
        dynamic_sidecar_settings.DYNAMIC_SIDECAR_PROXY_SETTINGS
    )

    # expose this service on an empty port
    endpint_spec = {}
    if dynamic_sidecar_settings.PROXY_EXPOSE_PORT:
        endpint_spec["Ports"] = [{"Protocol": "tcp", "TargetPort": 80}]

    return {
        "endpoint_spec": endpint_spec,
        "labels": {
            # TODO: let's use a pydantic model with descriptions
            "io.simcore.zone": f"{dynamic_sidecar_settings.TRAEFIK_SIMCORE_ZONE}",
            "swarm_stack_name": dynamic_sidecar_settings.SWARM_STACK_NAME,
            "traefik.docker.network": swarm_network_name,
            "traefik.enable": "true",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.customresponseheaders.Content-Security-Policy": f"frame-ancestors {scheduler_data.request_dns}",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accesscontrolallowmethods": "GET,OPTIONS,PUT,POST,DELETE,PATCH,HEAD",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accessControlAllowOriginList": f"{scheduler_data.request_scheme}://{scheduler_data.request_dns}",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accesscontrolmaxage": "100",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.addvaryheader": "true",
            f"traefik.http.services.{scheduler_data.proxy_service_name}.loadbalancer.server.port": "80",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.entrypoints": "http",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.priority": "10",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.rule": f"hostregexp(`{scheduler_data.node_uuid}.services.{{host:.+}}`)",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.middlewares": f"{dynamic_sidecar_settings.SWARM_STACK_NAME}_gzip@docker, {scheduler_data.proxy_service_name}-security-headers",
            "type": ServiceType.DEPENDENCY.value,
            "dynamic_type": "dynamic-sidecar",  # tagged as dynamic service
            "study_id": f"{scheduler_data.project_id}",
            "user_id": f"{scheduler_data.user_id}",
            "uuid": f"{scheduler_data.node_uuid}",  # needed for removal when project is closed
        },
        "name": scheduler_data.proxy_service_name,
        "networks": [swarm_network_id, dynamic_sidecar_network_id],
        "task_template": {
            "ContainerSpec": {
                "Env": {},
                "Hosts": [],
                "Image": f"caddy:{proxy_settings.DYNAMIC_SIDECAR_CADDY_VERSION}",
                "Init": True,
                "Labels": {},
                "Command": [
                    "caddy",
                    "reverse-proxy",
                    "--from",
                    ":80",
                    "--to",
                    f"{entrypoint_container_name}:{service_port}",
                ],
                "Mounts": mounts,
            },
            "Placement": {
                "Constraints": [
                    "node.platform.os == linux",
                    f"node.id == {dynamic_sidecar_node_id}",
                ]
            },
            "Resources": {
                "Limits": {"MemoryBytes": MEMORY_50MB, "NanoCPUs": CPU_1_PERCENT},
                "Reservations": {"MemoryBytes": MEMORY_50MB, "NanoCPUs": CPU_1_PERCENT},
            },
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": 5000000,
                "MaxAttempts": 100,
            },
        },
    }
