from typing import Any

from models_library.docker import StandardSimcoreDockerLabels
from models_library.services_resources import (
    CPU_10_PERCENT,
    CPU_100_PERCENT,
    MEMORY_50MB,
    MEMORY_250MB,
)
from pydantic import ByteSize

from ....core.settings import DynamicSidecarProxySettings, DynamicSidecarSettings
from ....models.schemas.dynamic_services import SchedulerData
from ._constants import DOCKER_CONTAINER_SPEC_RESTART_POLICY_DEFAULTS


def get_dynamic_proxy_spec(
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    swarm_network_name: str,
) -> dict[str, Any]:
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
    caddy_file = (
        f"{{\n admin 0.0.0.0:{proxy_settings.DYNAMIC_SIDECAR_CADDY_ADMIN_API_PORT} \n}}"
    )

    # expose this service on an empty port

    ports = []
    if dynamic_sidecar_settings.DYNAMIC_SIDECAR_EXPOSE_PORT:
        ports.append(
            # server port
            {
                "Protocol": "tcp",
                "TargetPort": proxy_settings.DYNAMIC_SIDECAR_CADDY_ADMIN_API_PORT,
            }
        )
    if dynamic_sidecar_settings.PROXY_EXPOSE_PORT:
        ports.append({"Protocol": "tcp", "TargetPort": 80})

    return {
        "endpoint_spec": {"Ports": ports} if ports else {},
        "labels": {
            # TODO: let's use a pydantic model with descriptions
            "io.simcore.zone": f"{dynamic_sidecar_settings.TRAEFIK_SIMCORE_ZONE}",
            "traefik.docker.network": swarm_network_name,
            "traefik.enable": "true",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.customresponseheaders.Content-Security-Policy": f"frame-ancestors {scheduler_data.request_dns} {scheduler_data.node_uuid}.services.{scheduler_data.request_dns}",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accesscontrolallowmethods": "GET,OPTIONS,PUT,POST,DELETE,PATCH,HEAD",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accessControlAllowOriginList": ",".join(
                [
                    f"{scheduler_data.request_scheme}://{scheduler_data.request_dns}",
                    f"{scheduler_data.request_scheme}://{scheduler_data.node_uuid}.services.{scheduler_data.request_dns}",
                ]
            ),
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accesscontrolmaxage": "100",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.addvaryheader": "true",
            f"traefik.http.services.{scheduler_data.proxy_service_name}.loadbalancer.server.port": "80",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.entrypoints": "http",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.priority": "10",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.rule": f"hostregexp(`{scheduler_data.node_uuid}.services.{{host:.+}}`)",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.middlewares": f"{dynamic_sidecar_settings.SWARM_STACK_NAME}_gzip@docker, {scheduler_data.proxy_service_name}-security-headers",
            "dynamic_type": "dynamic-sidecar",  # tagged as dynamic service
        }
        | StandardSimcoreDockerLabels(
            user_id=scheduler_data.user_id,
            project_id=scheduler_data.project_id,
            node_id=scheduler_data.node_uuid,
            product_name=scheduler_data.product_name,
            simcore_user_agent=scheduler_data.request_simcore_user_agent,
            swarm_stack_name=dynamic_sidecar_settings.SWARM_STACK_NAME,
            memory_limit=ByteSize(MEMORY_50MB),
            cpu_limit=float(CPU_10_PERCENT) / 1e9,
        ).to_simcore_runtime_docker_labels(),
        "name": scheduler_data.proxy_service_name,
        "networks": [swarm_network_id, dynamic_sidecar_network_id],
        "task_template": {
            "ContainerSpec": {
                "Env": {},
                "Hosts": [],
                "Image": f"caddy:{proxy_settings.DYNAMIC_SIDECAR_CADDY_VERSION}",
                "Init": True,
                "Labels": StandardSimcoreDockerLabels(
                    user_id=scheduler_data.user_id,
                    project_id=scheduler_data.project_id,
                    node_id=scheduler_data.node_uuid,
                    product_name=scheduler_data.product_name,
                    simcore_user_agent=scheduler_data.request_simcore_user_agent,
                    swarm_stack_name=dynamic_sidecar_settings.SWARM_STACK_NAME,
                    memory_limit=ByteSize(MEMORY_50MB),
                    cpu_limit=float(CPU_10_PERCENT) / 1e9,
                ).to_simcore_runtime_docker_labels(),
                "Command": [
                    "sh",
                    "-c",
                    f"echo -e '{caddy_file}' > /etc/caddy/Caddyfile && "
                    "cat /etc/caddy/Caddyfile && "
                    "caddy run --adapter caddyfile --config /etc/caddy/Caddyfile",
                ],
                "Mounts": mounts,
            },
            "Placement": {
                "Constraints": [
                    "node.platform.os == linux",
                    f"node.id == {scheduler_data.dynamic_sidecar.docker_node_id}",
                ]
            },
            "Resources": {
                "Reservations": {
                    "MemoryBytes": MEMORY_50MB,
                    "NanoCPUs": CPU_10_PERCENT,
                },
                "Limits": {"MemoryBytes": MEMORY_250MB, "NanoCPUs": CPU_100_PERCENT},
            },
            "RestartPolicy": DOCKER_CONTAINER_SPEC_RESTART_POLICY_DEFAULTS,
        },
    }
