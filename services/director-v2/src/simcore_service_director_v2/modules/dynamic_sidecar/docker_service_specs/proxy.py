from typing import Any

from models_library.docker import StandardSimcoreDockerLabels
from models_library.services_resources import (
    CPU_10_PERCENT,
    CPU_100_PERCENT,
    MEMORY_50MB,
    MEMORY_250MB,
)
from pydantic import ByteSize
from servicelib.common_headers import X_SIMCORE_USER_AGENT
from settings_library import webserver
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME

from ....core.dynamic_services_settings import DynamicServicesSettings
from ....core.dynamic_services_settings.proxy import DynamicSidecarProxySettings
from ....core.dynamic_services_settings.scheduler import (
    DynamicServicesSchedulerSettings,
)
from ....core.dynamic_services_settings.sidecar import DynamicSidecarSettings
from ....models.dynamic_services_scheduler import SchedulerData
from ._constants import DOCKER_CONTAINER_SPEC_RESTART_POLICY_DEFAULTS


def get_dynamic_proxy_spec(
    scheduler_data: SchedulerData,
    dynamic_services_settings: DynamicServicesSettings,
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
    assert (
        scheduler_data.product_name is not None
    ), "ONLY for legacy. This function should not be called with product_name==None"  # nosec

    proxy_settings: DynamicSidecarProxySettings = (
        dynamic_services_settings.DYNAMIC_SIDECAR_PROXY_SETTINGS
    )
    dynamic_sidecar_settings: DynamicSidecarSettings = (
        dynamic_services_settings.DYNAMIC_SIDECAR
    )
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings = (
        dynamic_services_settings.DYNAMIC_SCHEDULER
    )
    wb_auth_settings: webserver.WebServerSettings = (
        dynamic_services_settings.WEBSERVER_AUTH_SETTINGS
    )

    mounts = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
            "ReadOnly": True,
        }
    ]
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
    if proxy_settings.PROXY_EXPOSE_PORT:
        ports.append({"Protocol": "tcp", "TargetPort": 80})

    return {
        "endpoint_spec": {"Ports": ports} if ports else {},
        "labels": {
            "io.simcore.zone": f"{dynamic_services_scheduler_settings.TRAEFIK_SIMCORE_ZONE}",
            "traefik.swarm.network": swarm_network_name,
            "traefik.enable": "true",
            # security
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accesscontrolallowcredentials": "true",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.customresponseheaders.Content-Security-Policy": f"frame-ancestors {scheduler_data.request_dns} {scheduler_data.node_uuid}.services.{scheduler_data.request_dns}",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accesscontrolallowmethods": "GET,OPTIONS,PUT,POST,DELETE,PATCH,HEAD",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accesscontrolallowheaders": f"{X_SIMCORE_USER_AGENT},Set-Cookie",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accessControlAllowOriginList": ",".join(
                [
                    f"{scheduler_data.request_scheme}://{scheduler_data.request_dns}",
                    f"{scheduler_data.request_scheme}://{scheduler_data.node_uuid}.services.{scheduler_data.request_dns}",
                ]
            ),
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accesscontrolmaxage": "100",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.addvaryheader": "true",
            # auth
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-auth.forwardauth.address": f"{wb_auth_settings.api_base_url}/auth:check",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-auth.forwardauth.trustForwardHeader": "true",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-auth.forwardauth.authResponseHeaders": f"Set-Cookie,{DEFAULT_SESSION_COOKIE_NAME}",
            # routing
            f"traefik.http.services.{scheduler_data.proxy_service_name}.loadbalancer.server.port": "80",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.entrypoints": "http",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.priority": "10",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.rule": rf"HostRegexp(`{scheduler_data.node_uuid}\.services\.(?P<host>.+)`)",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.middlewares": ",".join(
                [
                    f"{dynamic_services_scheduler_settings.SWARM_STACK_NAME}_gzip@swarm",
                    f"{scheduler_data.proxy_service_name}-security-headers",
                    f"{scheduler_data.proxy_service_name}-auth",
                ]
            ),
            "dynamic_type": "dynamic-sidecar",  # tagged as dynamic service
        }
        | StandardSimcoreDockerLabels(
            user_id=scheduler_data.user_id,
            project_id=scheduler_data.project_id,
            node_id=scheduler_data.node_uuid,
            product_name=scheduler_data.product_name,
            simcore_user_agent=scheduler_data.request_simcore_user_agent,
            swarm_stack_name=dynamic_services_scheduler_settings.SWARM_STACK_NAME,
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
                    swarm_stack_name=dynamic_services_scheduler_settings.SWARM_STACK_NAME,
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
