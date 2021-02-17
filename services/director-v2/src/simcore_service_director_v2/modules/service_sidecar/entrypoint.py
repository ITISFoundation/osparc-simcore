import logging
from pathlib import Path
from typing import Any, Dict

from aiohttp import web

from .config import ServiceSidecarSettings, get_settings
from .constants import (
    FIXED_SERVICE_NAME_PROXY,
    FIXED_SERVICE_NAME_SIDECAR,
    SERVICE_SIDECAR_PREFIX,
)
from .docker_utils import (
    create_network,
    create_service_and_get_id,
    get_swarm_network,
    get_swarm_container_for_service,
)
from .monitor import get_monitor
from .utils import unused_port

log = logging.getLogger(__name__)


def strip_service_name(service_name: str) -> str:
    """returns: the maximum allowed service name in docker swarm"""
    return service_name[:63]


def assemble_service_name(
    project_id: str, service_key: str, node_uuid: str, fixed_service: str
) -> str:
    first_two_project_id = project_id[:2]
    name_from_service_key = service_key.split("/")[-1]
    return strip_service_name(
        f"{SERVICE_SIDECAR_PREFIX}_{node_uuid}_{first_two_project_id}"
        f"_{fixed_service}_{name_from_service_key}"
    )


async def stop_service_sidecar_stack_for_service(
    app: web.Application, node_uuid: str
) -> None:
    """will trigger actions needed to stop the service: removal from monitoring"""
    monitor = get_monitor(app)
    await monitor.remove_service_from_monitor(node_uuid)


async def start_service_sidecar_stack_for_service(  # pylint: disable=too-many-arguments
    app: web.Application,
    user_id: str,
    project_id: str,
    service_key: str,
    service_tag: str,
    node_uuid: str,
) -> Dict:
    debug_message = (
        f"SERVICE_SIDECAR: user_id={user_id}, project_id={project_id}, service_key={service_key}, "
        f"service_tag={service_tag}, node_uuid={node_uuid}"
    )
    # TODO: change the current interface , parameters will be ignored by this service
    # - internal_network_id
    # - node_base_path
    # - main_service

    log.debug(debug_message)

    service_sidecar_settings: ServiceSidecarSettings = get_settings(app)

    # Service naming schema:
    # -  srvsdcr_{uuid}_{first_two_project_id}_proxy_{name_from_service_key}
    # -  srvsdcr_{uuid}_{first_two_project_id}_sidecar_{name_from_service_key}

    service_name_service_sidecar = assemble_service_name(
        project_id, service_key, node_uuid, FIXED_SERVICE_NAME_SIDECAR
    )
    service_name_proxy = assemble_service_name(
        project_id, service_key, node_uuid, FIXED_SERVICE_NAME_PROXY
    )

    first_two_project_id = project_id[:2]

    # unique name for the traefik constraints
    io_simcore_zone = f"{SERVICE_SIDECAR_PREFIX}_{node_uuid}_{first_two_project_id}"

    # based on the node_id and project_id
    service_sidecar_network_name = (
        f"{SERVICE_SIDECAR_PREFIX}_{node_uuid}_{first_two_project_id}"
    )
    # these configuration should guarantee 245 address network
    network_config = {
        "Name": service_sidecar_network_name,
        "Driver": "overlay",
        "Labels": {
            "io.simcore.zone": f"{service_sidecar_settings.traefik_simcore_zone}",
            "com.simcore.description": f"interactive for node: {node_uuid}_{first_two_project_id}",
            "uuid": node_uuid,  # needed for removal when project is closed
        },
        "Attachable": True,
        "Internal": False,
    }
    service_sidecar_network_id = await create_network(network_config)

    # attach the service to the swarm network dedicated to services
    swarm_network = await get_swarm_network(service_sidecar_settings)
    swarm_network_id = swarm_network["Id"]
    swarm_network_name = swarm_network["Name"]

    # TODO: invert order of service startup
    # - start the service and then position the sidecar side to side on the same node

    service_sidecar_meta_data = await _dyn_service_sidecar_assembly(
        service_sidecar_settings=service_sidecar_settings,
        io_simcore_zone=io_simcore_zone,
        service_sidecar_network_name=service_sidecar_network_name,
        service_sidecar_network_id=service_sidecar_network_id,
        swarm_network_id=swarm_network_id,
        service_sidecar_name=service_name_service_sidecar,
        user_id=user_id,
        node_uuid=node_uuid,
        service_key=service_key,
        service_tag=service_tag,
        project_id=project_id,
    )

    service_sidecar_id = await create_service_and_get_id(service_sidecar_meta_data)
    logging.debug("sidecar-service id %s", service_sidecar_id)

    # TODO: finish here once migrated to director-v2
    task_data = await get_swarm_container_for_service(service_sidecar_id)
    logging.debug("Task inspect data %s", task_data)

    service_sidecar_proxy_meta_data = await _dyn_proxy_entrypoint_assembly(
        service_sidecar_settings=service_sidecar_settings,
        node_uuid=node_uuid,
        io_simcore_zone=io_simcore_zone,
        service_sidecar_network_name=service_sidecar_network_name,
        service_sidecar_network_id=service_sidecar_network_id,
        service_name=service_name_proxy,
        swarm_network_id=swarm_network_id,
        swarm_network_name=swarm_network_name,
        user_id=user_id,
        project_id=project_id,
    )

    service_sidecar_proxy_id = await create_service_and_get_id(
        service_sidecar_proxy_meta_data
    )
    logging.debug("sidecar-service-proxy id %s", service_sidecar_proxy_id)

    # services where successfully started and they can be monitored
    monitor = get_monitor(app)
    await monitor.add_service_to_monitor(
        service_name=service_name_service_sidecar,
        node_uuid=node_uuid,
        hostname=service_name_service_sidecar,
        port=service_sidecar_settings.web_service_port,
        service_key=service_key,
        service_tag=service_tag,
        service_sidecar_network_name=service_sidecar_network_name,
        simcore_traefik_zone=io_simcore_zone,
    )

    return service_sidecar_proxy_meta_data


async def _dyn_proxy_entrypoint_assembly(  # pylint: disable=too-many-arguments
    service_sidecar_settings: ServiceSidecarSettings,
    node_uuid: str,
    io_simcore_zone: str,
    service_sidecar_network_name: str,
    service_sidecar_network_id: str,
    service_name: str,
    swarm_network_id: str,
    swarm_network_name: str,
    user_id: str,
    project_id: str,
) -> Dict[str, Any]:
    """This is the entrypoint to the network and needs to be configured properly"""

    mounts = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
        }
    ]

    return {
        # "endpoint_spec": {"Mode": "dnsrr"},
        "labels": {
            "io.simcore.zone": f"{service_sidecar_settings.traefik_simcore_zone}",
            "port": "80",
            "swarm_stack_name": service_sidecar_settings.swarm_stack_name,
            "traefik.docker.network": swarm_network_name,
            "traefik.enable": "true",
            f"traefik.http.routers.{service_name}.entrypoints": "http",
            f"traefik.http.routers.{service_name}.middlewares": "master-simcore_gzip@docker",
            f"traefik.http.routers.{service_name}.priority": "10",
            # http://bb08a588-62b8-48a4-a459-7a61b4d47199.services.10.43.103.168.xip.io:9081
            f"traefik.http.routers.{service_name}.rule": f"hostregexp(`{node_uuid}.services.{{host:.+}}`)",
            f"traefik.http.services.{service_name}.loadbalancer.server.port": "80",
            "type": "dependency",
            "study_id": project_id,
            "user_id": user_id,
            "uuid": node_uuid,  # needed for removal when project is closed
        },
        "name": service_name,
        "networks": [swarm_network_id, service_sidecar_network_id],
        "task_template": {
            "ContainerSpec": {
                "Env": {},
                "Hosts": [],
                "Image": "traefik:v2.2.1",
                "Init": True,
                "Labels": {},
                "Command": [
                    "traefik",
                    "--log.level=DEBUG",
                    "--accesslog=true",
                    "--entryPoints.http.address=:80",
                    "--entryPoints.http.forwardedHeaders.insecure",
                    "--providers.docker.endpoint=unix:///var/run/docker.sock",
                    f"--providers.docker.network={service_sidecar_network_name}",
                    "--providers.docker.exposedByDefault=false",
                    f"--providers.docker.constraints=Label(`io.simcore.zone`, `{io_simcore_zone}`)",
                    # inject basic auth https://doc.traefik.io/traefik/v2.0/middlewares/basicauth/
                    # TODO: attach new auth_url to the service and make it available in the monitor
                    # use md5 for generating the passwords
                    # replace '$' with '$$'
                ],
                "Mounts": mounts,
            },
            # TODO: maybe remove these constraints? ask SAN
            "Placement": {"Constraints": ["node.platform.os == linux"]},
            "Resources": {
                "Limits": {"MemoryBytes": 1073741824, "NanoCPUs": 2000000000},
                "Reservations": {"MemoryBytes": 524288000, "NanoCPUs": 100000000},
            },
            # TODO: need to think what to do in this situation...
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": 5000000,
                "MaxAttempts": 2,
            },
        },
    }


async def _dyn_service_sidecar_assembly(  # pylint: disable=too-many-arguments
    service_sidecar_settings: ServiceSidecarSettings,
    io_simcore_zone: str,
    service_sidecar_network_name: str,
    service_sidecar_network_id: str,
    swarm_network_id: str,
    service_sidecar_name: str,
    user_id: str,
    node_uuid: str,
    service_key: str,
    service_tag: str,
    project_id: str,
) -> Dict[str, Any]:
    """This service contains the service-sidecar which will spawn the dynamic service itself """
    mounts = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
        }
    ]

    endpint_spec = {}

    if service_sidecar_settings.is_dev_mode:
        service_sidecar_path = service_sidecar_settings.dev_simcore_service_sidecar_path
        if service_sidecar_path is None:
            log.error(
                "Could not mount the sources for the service-sidecar, please provide env var named %s",
                service_sidecar_settings.dev_simcore_service_sidecar_path.__name__,
            )
        else:
            mounts.append(
                {
                    "Source": str(service_sidecar_path),
                    "Target": "/devel/services/service-sidecar",
                    "Type": "bind",
                }
            )
            packages_pacth = (
                Path(service_sidecar_settings.dev_simcore_service_sidecar_path)
                / ".."
                / ".."
                / "packages"
            )
            mounts.append(
                {
                    "Source": str(packages_pacth),
                    "Target": "/devel/packages",
                    "Type": "bind",
                }
            )
        # expose this service on an empty port
        if service_sidecar_settings.dev_expose_service_sidecar:
            endpint_spec["Ports"] = [
                {
                    "Protocol": "tcp",
                    "PublishedPort": unused_port(),
                    "TargetPort": service_sidecar_settings.web_service_port,
                }
            ]

    # used for the container name to avoid collisions for started containers on the same node
    compose_namespace = f"{SERVICE_SIDECAR_PREFIX}_{project_id}_{node_uuid}"

    return {
        # "auth": {"password": "adminadmin", "username": "admin"},   # maybe not needed together with registry
        "endpoint_spec": endpint_spec,
        "labels": {
            "io.simcore.zone": io_simcore_zone,
            "port": f"{service_sidecar_settings.web_service_port}",
            "study_id": project_id,
            "traefik.docker.network": service_sidecar_network_name,  # also used for monitoring
            "traefik.enable": "true",
            f"traefik.http.routers.{service_sidecar_name}.entrypoints": "http",
            f"traefik.http.routers.{service_sidecar_name}.priority": "10",
            f"traefik.http.routers.{service_sidecar_name}.rule": "PathPrefix(`/`)",
            f"traefik.http.services.{service_sidecar_name}.loadbalancer.server.port": f"{service_sidecar_settings.web_service_port}",
            "type": "dependency",
            "user_id": user_id,
            # the following are used for monitoring
            "uuid": node_uuid,  # also needed for removal when project is closed
            "swarm_stack_name": service_sidecar_settings.swarm_stack_name,
            "service_key": service_key,
            "service_tag": service_tag,
        },
        "name": service_sidecar_name,
        "networks": [swarm_network_id, service_sidecar_network_id],
        "task_template": {
            "ContainerSpec": {
                "Env": {
                    "POSTGRES_DB": "simcoredb",
                    "POSTGRES_ENDPOINT": "postgres: 5432",
                    "POSTGRES_PASSWORD": "adminadmin",
                    "POSTGRES_USER": "scu",
                    "SIMCORE_HOST_NAME": service_sidecar_name,
                    "STORAGE_ENDPOINT": "storage: 8080",
                    "SERVICE_SIDECAR_COMPOSE_NAMESPACE": compose_namespace,
                    "SERVICE_SIDECAR_DOCKER_COMPOSE_DOWN_TIMEOUT": service_sidecar_settings.service_sidecar_api_request_docker_compose_down_timeout,
                },
                "Hosts": [],
                "Image": service_sidecar_settings.image,
                "Init": True,
                "Labels": {},
                "Mounts": mounts,
            },
            "Placement": {"Constraints": ["node.platform.os == linux"]},
            "Resources": {
                "Limits": {"MemoryBytes": 1073741824, "NanoCPUs": 2000000000},
                "Reservations": {"MemoryBytes": 524288000, "NanoCPUs": 100000000},
            },
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": 5000000,
                "MaxAttempts": 2,
            },
        },
    }
