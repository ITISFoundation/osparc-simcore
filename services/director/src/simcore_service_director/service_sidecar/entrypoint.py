import logging

from typing import Dict, Optional

import aiodocker
from aiohttp import web

from .. import exceptions, config
from ..utils import get_swarm_network
from .monitor import get_monitor


log = logging.getLogger(__name__)

FIXED_SERVICE_NAME_SIDECAR = "sidecar"
FIXED_SERVICE_NAME_PROXY = "proxy"


def strip_service_name(service_name: str) -> str:
    """returns: the maximum allowed service name in docker swarm"""
    return service_name[:63]


def get_service_name_proxy(
    project_id: str, service_key: str, node_uuid: str, fixed_service: str
) -> str:
    first_two_project_id = project_id[:2]
    name_from_service_key = service_key.split("/")[-1]
    return strip_service_name(
        f"srvsdcr_{node_uuid}_{first_two_project_id}-{fixed_service}-{name_from_service_key}"
    )


async def stop_service_sidecar_stack_for_service(
    app: web.Application, node_uuid: str
) -> None:
    """will trigger actions needed to stop the service: removal from monitoring"""
    monitor = get_monitor(app)
    monitor.remove_service_from_monitor(node_uuid)


async def start_service_sidecar_stack_for_service(
    app: web.Application,
    client: aiodocker.docker.Docker,
    user_id: str,
    project_id: str,
    service_key: str,
    service_tag: str,
    main_service: bool,
    node_uuid: str,
    node_base_path: str,
    internal_network_id: Optional[str],
) -> Dict:
    """start the monitoring before spawning the process and remove the monitoring 
    in case an exception occurs, also continue propagating the exception.
    """
    monitor = get_monitor(app)

    service_name = get_service_name_proxy(
        project_id=project_id,
        service_key=service_key,
        node_uuid=node_uuid,
        fixed_service=FIXED_SERVICE_NAME_SIDECAR,
    )
    try:
        await monitor.add_service_to_monitor(
            service_name=service_name, node_uuid=node_uuid
        )
        return await _wrapped_start_service_sidecar_stack_for_service(
            client=client,
            user_id=user_id,
            project_id=project_id,
            service_key=service_key,
            service_tag=service_tag,
            main_service=main_service,
            node_uuid=node_uuid,
            node_base_path=node_base_path,
            internal_network_id=internal_network_id,
        )
    except Exception:
        await monitor.remove_service_from_monitor(node_uuid)
        raise


async def _wrapped_start_service_sidecar_stack_for_service(
    client: aiodocker.docker.Docker,
    user_id: str,
    project_id: str,
    service_key: str,
    service_tag: str,
    main_service: bool,
    node_uuid: str,
    node_base_path: str,
    internal_network_id: Optional[str],
) -> Dict:
    debug_message = (
        f"SERVICE_SIDECAR: user_id={user_id}, project_id={project_id}, service_key={service_key}, "
        f"service_tag={service_tag}, main_service={main_service}, node_uuid={node_uuid}, "
        f"node_base_path={node_base_path}, internal_network_id={internal_network_id}"
    )
    # TODO: change the current interface , parameters will be ignored by this service
    # - internal_network_id
    # - node_base_path
    # - main_service

    log.debug(debug_message)

    # Service naming schema:
    # -  srvsdcr_{uuid}_{first_two_project_id}-proxy-{name_from_service_key}
    # -  srvsdcr_{uuid}_{first_two_project_id}-sidecar-{name_from_service_key}

    service_name_service_sidecar = get_service_name_proxy(
        project_id, service_key, node_uuid, FIXED_SERVICE_NAME_SIDECAR
    )
    service_name_proxy = get_service_name_proxy(
        project_id, service_key, node_uuid, FIXED_SERVICE_NAME_PROXY
    )

    first_two_project_id = project_id[:2]

    # unique name for the traefik constraints
    io_simcore_zone = f"service_sidecar_{node_uuid}_{first_two_project_id}"

    # the 'serv_side_' is used to be easily garabage collected if the
    # network is not attached to any other containers
    service_sidecar_network_name = f"serv_side_{node_uuid}_{first_two_project_id}"  # based on the node_id and project_id
    # these configuration should guarantee 245 address network
    network_config = {
        "Name": service_sidecar_network_name,
        "Driver": "overlay",
        "Labels": {
            "io.simcore.zone": f"{config.TRAEFIK_SIMCORE_ZONE}",
            "com.simcore.description": f"interactive for node: {node_uuid}_{first_two_project_id}",
            "uuid": node_uuid,  # needed for removal when project is closed
        },
        "Attachable": True,
        "Internal": False,
    }
    try:
        service_sidecar_network_id = (await client.networks.create(network_config)).id
    except aiodocker.exceptions.DockerError as err:
        log.exception("Error while creating network %s", service_sidecar_network_name)
        raise exceptions.GenericDockerError(
            "Error while creating network", err
        ) from err

    # attach the service to the swarm network dedicated to services
    swarm_network = await get_swarm_network(client)
    swarm_network_id = swarm_network["Id"]
    swarm_network_name = swarm_network["Name"]

    sidecar_service_proxy_meta_data = await _dyn_proxy_entrypoint_assembly(
        node_uuid=node_uuid,
        io_simcore_zone=io_simcore_zone,
        service_sidecar_network_name=service_sidecar_network_name,
        service_sidecar_network_id=service_sidecar_network_id,
        service_name=service_name_proxy,
        swarm_network_id=swarm_network_id,
        swarm_network_name=swarm_network_name,
        user_id=user_id,
    )

    log.debug("NEW_SERVICE_PROXY %s", sidecar_service_proxy_meta_data)

    service_start_result = await client.services.create(
        **sidecar_service_proxy_meta_data
    )
    if "ID" not in service_start_result:
        raise exceptions.DirectorException(
            "Error while starting service: {}".format(str(service_start_result))
        )

    sidecar_service_meta_data = await _dyn_service_sidecar_assembly(
        io_simcore_zone=io_simcore_zone,
        service_sidecar_network_name=service_sidecar_network_name,
        service_sidecar_network_id=service_sidecar_network_id,
        swarm_network_id=swarm_network_id,
        service_sidecar_name=service_name_service_sidecar,
        user_id=user_id,
        node_uuid=node_uuid,
    )

    log.debug("NEW_SERVICE %s", sidecar_service_meta_data)

    service_start_result = await client.services.create(**sidecar_service_meta_data)
    if "ID" not in service_start_result:
        raise exceptions.DirectorException(
            "Error while starting service: {}".format(str(service_start_result))
        )

    return sidecar_service_proxy_meta_data


async def _dyn_proxy_entrypoint_assembly(
    node_uuid: str,
    io_simcore_zone: str,
    service_sidecar_network_name: str,
    service_sidecar_network_id: str,
    service_name: str,
    swarm_network_id: str,
    swarm_network_name: str,
    user_id: str,
):
    """This is the entrypoint to the network and needs to be configured properly"""

    mounts = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
        }
    ]

    # TODO: it needs to proxy the services form the network
    # - also it needs to be discoverable, right now we have issues and it is not visible

    return {
        "endpoint_spec": {"Mode": "dnsrr"},
        "labels": {
            "io.simcore.zone": f"{config.TRAEFIK_SIMCORE_ZONE}",
            "port": "80",
            "swarm_stack_name": config.SWARM_STACK_NAME,
            "traefik.docker.network": swarm_network_name,
            "traefik.enable": "true",
            f"traefik.http.routers.{service_name}.entrypoints": "http",
            f"traefik.http.routers.{service_name}.middlewares": "master-simcore_gzip@docker",
            f"traefik.http.routers.{service_name}.priority": "10",
            f"traefik.http.routers.{service_name}.rule": "Host(`entrypoint.services.10.43.103.168.xip.io`)",  # TODO: change entrypoint -> node_uuid
            f"traefik.http.services.{service_name}.loadbalancer.server.port": "80",
            "type": "dependency",
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
                    "--providers.docker.swarmMode=true",
                    "--providers.docker.exposedByDefault=false",
                    f"--providers.docker.constraints=Label(`io.simcore.zone`, `{io_simcore_zone}`)",
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


async def _dyn_service_sidecar_assembly(
    io_simcore_zone: str,
    service_sidecar_network_name: str,
    service_sidecar_network_id: str,
    swarm_network_id: str,
    service_sidecar_name: str,
    user_id: str,
    node_uuid: str,
):
    """This service contains the service-sidecar which will spawn the dynamic service itself """
    mounts = []

    # TODO: ask SAN how to check for dev mode to be 100% sure
    is_development_mode = True
    if is_development_mode:
        service_sidecar_path = config.DEV_SIMCORE_SERVICE_SIDECAR_PATH
        if service_sidecar_path is None:
            log.error(
                "Could not mount the sources for the service-sidecar, please provide env var named %s",
                config.DEV_SIMCORE_SERVICE_SIDECAR_PATH.__name__,
            )
        else:
            mounts.append(
                {
                    "Source": str(service_sidecar_path),
                    "Target": "/devel/services/service-sidecar",
                    "Type": "bind",
                }
            )

    return {
        # "auth": {"password": "adminadmin", "username": "admin"},   # maybe not needed together with registry
        "endpoint_spec": {"Mode": "dnsrr"},
        "labels": {
            "io.simcore.zone": io_simcore_zone,
            "port": "8000",
            "study_id": "4b46c1d2-2d92-11eb-8066-02420a0000fe",
            "swarm_stack_name": "master-simcore",  # nope, needs to change to custom
            "traefik.docker.network": service_sidecar_network_name,
            "traefik.enable": "true",
            f"traefik.http.routers.{service_sidecar_name}.entrypoints": "http",
            f"traefik.http.routers.{service_sidecar_name}.priority": "10",
            f"traefik.http.routers.{service_sidecar_name}.rule": "PathPrefix(`/`)",
            f"traefik.http.services.{service_sidecar_name}.loadbalancer.server.port": "8000",
            "type": "dependency",
            "user_id": user_id,
            "uuid": node_uuid,  # needed for removal when project is closed
        },
        "name": service_sidecar_name,
        "networks": [swarm_network_id, service_sidecar_network_id],
        # "registry": config.REGISTRY_URL,
        "task_template": {
            "ContainerSpec": {
                "Env": {
                    "POSTGRES_DB": "simcoredb",
                    "POSTGRES_ENDPOINT": "postgres: 5432",
                    "POSTGRES_PASSWORD": "adminadmin",
                    "POSTGRES_USER": "scu",
                    "SIMCORE_HOST_NAME": service_sidecar_name,
                    "STORAGE_ENDPOINT": "storage: 8080",
                },
                "Hosts": [],
                "Image": config.SERVICE_SIDECAR_IMAGE,
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


# TODO: move this to separate module, not here

# TODO: make sure this service is up and running to start the rest of the things
# - check service is up, use some sort of queuing for this part the cheking etc, to put requests for monitoring
# - then assemble a docker-compose spec from a service, name and start the service
# -
