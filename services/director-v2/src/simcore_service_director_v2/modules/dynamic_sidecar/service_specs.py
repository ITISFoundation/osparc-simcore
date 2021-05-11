import logging
import json
from typing import Any, Dict, List, Optional

from uuid import UUID


from models_library.projects import ProjectID
from ...models.schemas.constants import UserID

from .config import DynamicSidecarSettings
from .constants import DYNAMIC_SIDECAR_PREFIX

from .utils import unused_port
from .exceptions import DynamicSidecarError
from ...models.domains.dynamic_sidecar import PathsMappingModel, ComposeSpecModel

MAX_ALLOWED_SERVICE_NAME_LENGTH: int = 63


log = logging.getLogger(__name__)


def _strip_service_name(service_name: str) -> str:
    """returns: the maximum allowed service name in docker swarm"""
    return service_name[:MAX_ALLOWED_SERVICE_NAME_LENGTH]


def assemble_service_name(
    project_id: ProjectID, service_key: str, node_uuid: UUID, constant_service: str
) -> str:
    first_two_project_id = str(project_id)[:2]
    name_from_service_key = service_key.split("/")[-1]
    return _strip_service_name(
        f"{DYNAMIC_SIDECAR_PREFIX}_{node_uuid}_{first_two_project_id}"
        f"_{constant_service}_{name_from_service_key}"
    )


def extract_service_port_from_compose_start_spec(
    create_service_params: Dict[str, Any]
) -> int:
    return create_service_params["labels"]["service_port"]


async def dyn_proxy_entrypoint_assembly(  # pylint: disable=too-many-arguments
    dynamic_sidecar_settings: DynamicSidecarSettings,
    node_uuid: UUID,
    io_simcore_zone: str,
    dynamic_sidecar_network_name: str,
    dynamic_sidecar_network_id: str,
    service_name: str,
    swarm_network_id: str,
    swarm_network_name: str,
    user_id: UserID,
    project_id: ProjectID,
    dynamic_sidecar_node_id: str,
    request_scheme: str,
    request_dns: str,
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
        "labels": {
            "io.simcore.zone": f"{dynamic_sidecar_settings.traefik_simcore_zone}",
            "swarm_stack_name": dynamic_sidecar_settings.swarm_stack_name,
            "traefik.docker.network": swarm_network_name,
            "traefik.enable": "true",
            f"traefik.http.middlewares.{service_name}-security-headers.headers.customresponseheaders.Content-Security-Policy": f"frame-ancestors {request_dns}",
            f"traefik.http.middlewares.{service_name}-security-headers.headers.accesscontrolallowmethods": "GET,OPTIONS,PUT,POST,DELETE,PATCH,HEAD",
            f"traefik.http.middlewares.{service_name}-security-headers.headers.accessControlAllowOriginList": f"{request_scheme}://{request_dns}",
            f"traefik.http.middlewares.{service_name}-security-headers.headers.accesscontrolmaxage": "100",
            f"traefik.http.middlewares.{service_name}-security-headers.headers.addvaryheader": "true",
            f"traefik.http.services.{service_name}.loadbalancer.server.port": "80",
            f"traefik.http.routers.{service_name}.entrypoints": "http",
            f"traefik.http.routers.{service_name}.priority": "10",
            f"traefik.http.routers.{service_name}.rule": f"hostregexp(`{node_uuid}.services.{{host:.+}}`)",
            f"traefik.http.routers.{service_name}.middlewares": f"master-simcore_gzip@docker, {service_name}-security-headers",
            "type": "main",  # main is required to be monitored by the frontend
            "dynamic_type": "dynamic-sidecar",  # tagged as dynamic service
            "study_id": f"{project_id}",
            "user_id": f"{user_id}",
            "uuid": f"{node_uuid}",  # needed for removal when project is closed
        },
        "name": service_name,
        "networks": [swarm_network_id, dynamic_sidecar_network_id],
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
                    f"--providers.docker.network={dynamic_sidecar_network_name}",
                    "--providers.docker.exposedByDefault=false",
                    f"--providers.docker.constraints=Label(`io.simcore.zone`, `{io_simcore_zone}`)",
                    # inject basic auth https://doc.traefik.io/traefik/v2.0/middlewares/basicauth/
                    # TODO: attach new auth_url to the service and make it available in the monitor
                ],
                "Mounts": mounts,
            },
            "Placement": {
                "Constraints": [
                    "node.platform.os == linux",  # TODO: ask SAN should this be removed?
                    f"node.id == {dynamic_sidecar_node_id}",
                ]
            },
            "Resources": {  # starts from 100 MB and maxes at 250 MB with 10% max CPU usage
                "Limits": {"MemoryBytes": 262144000, "NanoCPUs": 100000000},
                "Reservations": {"MemoryBytes": 104857600, "NanoCPUs": 100000000},
            },
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": 5000000,
                "MaxAttempts": 2,
            },
        },
    }


def _check_setting_correctness(setting: Dict) -> None:
    if "name" not in setting or "type" not in setting or "value" not in setting:
        raise DynamicSidecarError("Invalid setting in %s" % setting)


def _parse_mount_settings(settings: List[Dict]) -> List[Dict]:
    mounts = list()
    for s in settings:
        log.debug("Retrieved mount settings %s", s)
        mount = dict()
        mount["ReadOnly"] = True
        if "ReadOnly" in s and s["ReadOnly"] in ["false", "False", False]:
            mount["ReadOnly"] = False

        for field in ["Source", "Target", "Type"]:
            if field in s:
                mount[field] = s[field]
            else:
                log.warning(
                    "Mount settings have wrong format. Required keys [Source, Target, Type]"
                )
                continue

        log.debug("Append mount settings %s", mount)
        mounts.append(mount)

    return mounts


def _parse_env_settings(settings: List[str]) -> Dict:
    envs = dict()
    for s in settings:
        log.debug("Retrieved env settings %s", s)
        if "=" in s:
            parts = s.split("=")
            if len(parts) == 2:
                # will be forwarded to dynamic-sidecar spawned containers
                envs[f"FORWARD_ENV_{parts[0]}"] = parts[1]

        log.debug("Parsed env settings %s", s)

    return envs


# pylint: disable=too-many-branches
def _inject_settings_to_create_service_params(
    labels_service_settings: List[Dict[str, Any]],
    create_service_params: Dict[str, Any],
) -> None:
    for param in labels_service_settings:
        _check_setting_correctness(param)

        # NOTE: the below capitalize addresses a bug in a lot of already in use services
        # where Resources was written in lower case
        if param["type"].capitalize() == "Resources":
            # python-API compatible for backward compatibility
            if "mem_limit" in param["value"]:
                create_service_params["task_template"]["Resources"]["Limits"][
                    "MemoryBytes"
                ] = param["value"]["mem_limit"]
            if "cpu_limit" in param["value"]:
                create_service_params["task_template"]["Resources"]["Limits"][
                    "NanoCPUs"
                ] = param["value"]["cpu_limit"]
            if "mem_reservation" in param["value"]:
                create_service_params["task_template"]["Resources"]["Reservations"][
                    "MemoryBytes"
                ] = param["value"]["mem_reservation"]
            if "cpu_reservation" in param["value"]:
                create_service_params["task_template"]["Resources"]["Reservations"][
                    "NanoCPUs"
                ] = param["value"]["cpu_reservation"]
            # REST-API compatible
            if "Limits" in param["value"] or "Reservations" in param["value"]:
                create_service_params["task_template"]["Resources"].update(
                    param["value"]
                )

        # publishing port on the ingress network.
        elif param["name"] == "ports" and param["type"] == "int":  # backward comp
            create_service_params["labels"]["port"] = create_service_params["labels"][
                "service_port"
            ] = str(param["value"])
        # REST-API compatible
        elif param["type"] == "EndpointSpec":
            if "Ports" in param["value"]:
                if (
                    isinstance(param["value"]["Ports"], list)
                    and "TargetPort" in param["value"]["Ports"][0]
                ):
                    create_service_params["labels"]["port"] = create_service_params[
                        "labels"
                    ]["service_port"] = str(param["value"]["Ports"][0]["TargetPort"])

        # placement constraints
        elif param["name"] == "constraints":  # python-API compatible
            create_service_params["task_template"]["Placement"]["Constraints"] += param[
                "value"
            ]
        elif param["type"] == "Constraints":  # REST-API compatible
            create_service_params["task_template"]["Placement"]["Constraints"] += param[
                "value"
            ]
        elif param["name"] == "env":
            log.debug("Found env parameter %s", param["value"])
            env_settings = _parse_env_settings(param["value"])
            if env_settings:
                create_service_params["task_template"]["ContainerSpec"]["Env"].update(
                    env_settings
                )
        elif param["name"] == "mount":
            log.debug("Found mount parameter %s", param["value"])
            mount_settings: List[Dict] = _parse_mount_settings(param["value"])
            if mount_settings:
                create_service_params["task_template"]["ContainerSpec"][
                    "Mounts"
                ].extend(mount_settings)

    container_spec = create_service_params["task_template"]["ContainerSpec"]
    # set labels for CPU and Memory limits
    container_spec["Labels"]["nano_cpus_limit"] = str(
        create_service_params["task_template"]["Resources"]["Limits"]["NanoCPUs"]
    )
    container_spec["Labels"]["mem_limit"] = str(
        create_service_params["task_template"]["Resources"]["Limits"]["MemoryBytes"]
    )


async def dynamic_sidecar_assembly(  # pylint: disable=too-many-arguments
    dynamic_sidecar_settings: DynamicSidecarSettings,
    io_simcore_zone: str,
    dynamic_sidecar_network_name: str,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    dynamic_sidecar_name: str,
    user_id: UserID,
    node_uuid: UUID,
    service_key: str,
    service_tag: str,
    paths_mapping: PathsMappingModel,
    compose_spec: ComposeSpecModel,
    target_container: Optional[str],
    project_id: ProjectID,
    settings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """This service contains the dynamic-sidecar which will spawn the dynamic service itself """
    mounts = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
        }
    ]

    endpint_spec = {}

    if dynamic_sidecar_settings.is_dev_mode:
        dynamic_sidecar_path = dynamic_sidecar_settings.dev_simcore_dynamic_sidecar_path
        if dynamic_sidecar_path is None:
            log.warning(
                (
                    "Could not mount the sources for the dynamic-sidecar, please "
                    "provide env var named DEV_SIMCORE_DYNAMIC_SIDECAR_PATH"
                )
            )
        else:
            mounts.append(
                {
                    "Source": str(dynamic_sidecar_path),
                    "Target": "/devel/services/dynamic-sidecar",
                    "Type": "bind",
                }
            )
            packages_pacth = (
                dynamic_sidecar_settings.dev_simcore_dynamic_sidecar_path
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
    if dynamic_sidecar_settings.dev_expose_dynamic_sidecar:
        endpint_spec["Ports"] = [
            {
                "Protocol": "tcp",
                "PublishedPort": unused_port(),
                "TargetPort": dynamic_sidecar_settings.web_service_port,
            }
        ]

    # used for the container name to avoid collisions for started containers on the same node
    compose_namespace = f"{DYNAMIC_SIDECAR_PREFIX}_{node_uuid}"

    create_service_params = {
        # "auth": {"password": "adminadmin", "username": "admin"},   # maybe not needed together with registry
        "endpoint_spec": endpint_spec,
        "labels": {
            "io.simcore.zone": io_simcore_zone,
            "port": f"{dynamic_sidecar_settings.web_service_port}",
            "study_id": f"{project_id}",
            "traefik.docker.network": dynamic_sidecar_network_name,  # also used for monitoring
            "traefik.enable": "true",
            f"traefik.http.routers.{dynamic_sidecar_name}.entrypoints": "http",
            f"traefik.http.routers.{dynamic_sidecar_name}.priority": "10",
            f"traefik.http.routers.{dynamic_sidecar_name}.rule": "PathPrefix(`/`)",
            f"traefik.http.services.{dynamic_sidecar_name}.loadbalancer.server.port": f"{dynamic_sidecar_settings.web_service_port}",
            "type": "dependency",
            "user_id": f"{user_id}",
            # the following are used for monitoring
            "uuid": f"{node_uuid}",  # also needed for removal when project is closed
            "swarm_stack_name": dynamic_sidecar_settings.swarm_stack_name,
            "service_key": service_key,
            "service_tag": service_tag,
            "paths_mapping": paths_mapping.json(),
            "compose_spec": json.dumps(compose_spec),
            "target_container": json.dumps(target_container),
        },
        "name": dynamic_sidecar_name,
        "networks": [swarm_network_id, dynamic_sidecar_network_id],
        "task_template": {
            "ContainerSpec": {
                "Env": {
                    "SIMCORE_HOST_NAME": dynamic_sidecar_name,
                    "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": compose_namespace,
                },
                "Hosts": [],
                "Image": dynamic_sidecar_settings.image,
                "Init": True,
                "Labels": {},
                "Mounts": mounts,
            },
            "Placement": {"Constraints": []},
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": 5000000,
                "MaxAttempts": 2,
            },
            # this will get overwritten
            "Resources": {
                "Limits": {"NanoCPUs": 2 * pow(10, 9), "MemoryBytes": 1 * pow(1024, 3)},
                "Reservations": {
                    "NanoCPUs": 1 * pow(10, 8),
                    "MemoryBytes": 500 * pow(1024, 2),
                },
            },
        },
    }

    _inject_settings_to_create_service_params(
        labels_service_settings=settings,
        create_service_params=create_service_params,
    )

    return create_service_params