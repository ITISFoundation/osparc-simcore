import asyncio
import json
import logging
from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import Any, AsyncGenerator, Final, NamedTuple, Optional

import aiodocker
from aiodocker import Docker
from dask_gateway_server.backends.db_base import Cluster, DBBackendBase
from yarl import URL

from .errors import NoHostFoundError, NoServiceTasksError, TaskNotAssignedError
from .models import ClusterInformation, Hostname, cluster_information_from_docker_nodes
from .settings import AppSettings

_SHARED_COMPUTATIONAL_FOLDER_IN_SIDECAR = "/home/scu/shared_computational_data"
_DASK_KEY_CERT_PATH_IN_SIDECAR = Path("/home/scu/dask-credentials")


class DockerSecret(NamedTuple):
    secret_id: str
    secret_name: str
    secret_file_name: str
    cluster: Cluster


async def is_service_task_running(
    docker_client: Docker, service_name: str, logger: logging.Logger
) -> bool:
    tasks = await docker_client.tasks.list(filters={"service": service_name})
    tasks_current_state = [task["Status"]["State"] for task in tasks]
    logger.info(
        "%s current service task states are %s", service_name, f"{tasks_current_state=}"
    )
    num_running = sum(current == "running" for current in tasks_current_state)
    return bool(num_running == 1)


async def get_network_id(
    docker_client: Docker, network_name: str, logger: logging.Logger
) -> str:
    # try to find the network name (usually named STACKNAME_default)
    logger.debug("--> finding network id for '%s'", f"{network_name=}")
    networks = [
        x
        for x in (await docker_client.networks.list())
        if "swarm" in x["Scope"] and network_name == x["Name"]
    ]
    logger.debug(f"found the following: {networks=}")
    if not networks:
        raise ValueError(f"network {network_name} not found")
    if len(networks) > 1:
        # NOTE: this is impossible at the moment. test_utils::test_get_network_id proves it
        raise ValueError(
            f"network {network_name} is ambiguous, too many network founds: {networks=}"
        )
    logger.debug("found '%s'", f"{networks[0]=}")
    assert "Id" in networks[0]  # nosec
    assert isinstance(networks[0]["Id"], str)  # nosec
    return networks[0]["Id"]


def create_service_config(
    settings: AppSettings,
    service_env: dict[str, Any],
    service_name: str,
    network_id: str,
    service_secrets: list[DockerSecret],
    cmd: Optional[list[str]],
    labels: dict[str, str],
    placement: Optional[dict[str, Any]],
    **service_kwargs,
) -> dict[str, Any]:
    env = deepcopy(service_env)
    env.pop("PATH", None)
    # create the secrets array containing the TLS cert/key pair
    container_secrets = []
    for s in service_secrets:
        container_secrets.append(
            {
                "SecretName": s.secret_name,
                "SecretID": s.secret_id,
                "File": {
                    "Name": f"{_DASK_KEY_CERT_PATH_IN_SIDECAR / Path(s.secret_file_name).name}",
                    "UID": "0",
                    "GID": "0",
                    "Mode": 0x777,
                },
            }
        )
        env_updates = {}
        for env_name, env_value in env.items():
            if env_value == s.secret_file_name:
                env_updates[
                    env_name
                ] = f"{_DASK_KEY_CERT_PATH_IN_SIDECAR / Path(s.secret_file_name).name}"
        env.update(env_updates)
    mounts = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
            "ReadOnly": True,
        },
        # the sidecar data data is stored in a volume
        {
            "Source": settings.COMPUTATIONAL_SIDECAR_VOLUME_NAME,
            "Target": _SHARED_COMPUTATIONAL_FOLDER_IN_SIDECAR,
            "Type": "volume",
            "ReadOnly": False,
        },
    ]

    task_template: dict[str, Any] = {
        "ContainerSpec": {
            "Env": env,
            "Image": settings.COMPUTATIONAL_SIDECAR_IMAGE,
            "Init": True,
            "Mounts": mounts,
            "Secrets": container_secrets,
            "Hostname": service_name,
        },
        "RestartPolicy": {"Condition": "on-failure"},
    }

    if cmd:
        task_template["ContainerSpec"]["Command"] = cmd
    if placement:
        task_template["Placement"] = placement

    return {
        "name": service_name,
        "labels": labels,
        "task_template": task_template,
        "networks": [network_id],
        **service_kwargs,
    }


async def create_or_update_secret(
    docker_client: aiodocker.Docker,
    target_file_name: str,
    cluster: Cluster,
    *,
    file_path: Optional[Path] = None,
    secret_data: Optional[str] = None,
) -> DockerSecret:
    if file_path is None and secret_data is None:
        raise ValueError(
            f"Both {file_path=} and {secret_data=} are empty, that is not allowed"
        )
    data = secret_data
    if not data and file_path:
        data = file_path.read_text()

    docker_secret_name = f"{Path( target_file_name).name}_{cluster.id}"

    secrets = await docker_client.secrets.list(filters={"name": docker_secret_name})
    if secrets:
        # we must first delete it as only labels may be updated
        secret = secrets[0]
        await docker_client.secrets.delete(secret["ID"])
    secret = await docker_client.secrets.create(
        name=docker_secret_name,
        data=data,
        labels={"cluster_id": f"{cluster.id}", "cluster_name": f"{cluster.name}"},
    )
    return DockerSecret(
        secret_id=secret["ID"],
        secret_name=docker_secret_name,
        secret_file_name=target_file_name,
        cluster=cluster,
    )


async def delete_secrets(docker_client: aiodocker.Docker, cluster: Cluster) -> None:
    secrets = await docker_client.secrets.list(
        filters={"label": f"cluster_id={cluster.id}"}
    )
    await asyncio.gather(*[docker_client.secrets.delete(s["ID"]) for s in secrets])


async def start_service(
    docker_client: aiodocker.Docker,
    settings: AppSettings,
    logger: logging.Logger,
    service_name: str,
    base_env: dict[str, str],
    cluster_secrets: list[DockerSecret],
    cmd: Optional[list[str]],
    labels: dict[str, str],
    gateway_api_url: str,
    placement: Optional[dict[str, Any]] = None,
    **service_kwargs,
) -> AsyncGenerator[dict[str, Any], None]:
    service_parameters = {}
    try:
        assert settings.COMPUTATIONAL_SIDECAR_LOG_LEVEL  # nosec
        env = deepcopy(base_env)
        env.update(
            {
                # NOTE: the hostname of the gateway API must be
                # modified so that the scheduler/sidecar can
                # send heartbeats to the gateway
                "DASK_GATEWAY_API_URL": f"{URL(gateway_api_url).with_host(settings.GATEWAY_SERVER_NAME)}",
                "SIDECAR_COMP_SERVICES_SHARED_FOLDER": _SHARED_COMPUTATIONAL_FOLDER_IN_SIDECAR,
                "SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME": settings.COMPUTATIONAL_SIDECAR_VOLUME_NAME,
                "LOG_LEVEL": settings.COMPUTATIONAL_SIDECAR_LOG_LEVEL,
            }
        )

        # find service parameters
        network_id = await get_network_id(
            docker_client, settings.GATEWAY_WORKERS_NETWORK, logger
        )
        service_parameters = create_service_config(
            settings,
            env,
            service_name,
            network_id,
            cluster_secrets,
            cmd,
            labels=labels,
            placement=placement,
            **service_kwargs,
        )

        # start service
        logger.info("Starting service %s", service_name)
        logger.debug("Using parameters %s", json.dumps(service_parameters, indent=2))
        service = await docker_client.services.create(**service_parameters)
        logger.info("Service %s started: %s", service_name, f"{service=}")
        yield {"service_id": service["ID"]}

        # get the full info from docker
        service = await docker_client.services.inspect(service["ID"])
        logger.debug(
            "Service '%s' inspection: %s",
            service_name,
            f"{json.dumps(service, indent=2)}",
        )

        # wait until the service is started
        logger.info(
            "---> Service started, waiting for service %s to run...",
            service_name,
        )
        while not await is_service_task_running(
            docker_client, service["Spec"]["Name"], logger
        ):
            yield {"service_id": service["ID"]}
            await asyncio.sleep(1)

        # we are done, the service is started
        logger.info(
            "---> Service %s is started, and has ID %s",
            service["Spec"]["Name"],
            service["ID"],
        )
        yield {"service_id": service["ID"]}

    except (aiodocker.DockerContainerError, aiodocker.DockerError):
        logger.exception(
            "Unexpected Error while running container with parameters %s",
            json.dumps(service_parameters, indent=2),
        )
        raise
    except asyncio.CancelledError:
        logger.warn("Service creation was cancelled")
        raise


async def stop_service(
    docker_client: aiodocker.Docker, service_id: str, logger: logging.Logger
) -> None:
    logger.info("Stopping service %s", f"{service_id}")
    try:
        await docker_client.services.delete(service_id)
        logger.info("service %s stopped", f"{service_id=}")

    except aiodocker.DockerContainerError:
        logger.exception("Error while stopping service with id %s", f"{service_id=}")


async def create_docker_secrets_from_tls_certs_for_cluster(
    docker_client: Docker, backend: DBBackendBase, cluster: Cluster
) -> list[DockerSecret]:
    tls_cert_path, tls_key_path = backend.get_tls_paths(cluster)
    return [
        await create_or_update_secret(
            docker_client,
            f"{tls_cert_path}",
            cluster,
            secret_data=cluster.tls_cert.decode(),
        ),
        await create_or_update_secret(
            docker_client,
            f"{tls_key_path}",
            cluster,
            secret_data=cluster.tls_key.decode(),
        ),
    ]


OSPARC_SCHEDULER_API_PORT: Final[int] = 8786
OSPARC_SCHEDULER_DASHBOARD_PORT: Final[int] = 8787


def get_osparc_scheduler_cmd_modifications(
    scheduler_service_name: str,
) -> dict[str, str]:
    # NOTE: the healthcheck of itisfoundation/dask-sidecar expects the dashboard
    # to be on port 8787
    # (see https://github.com/ITISFoundation/osparc-simcore/blob/f3d98dccdae665d23701b0db4ee917364a0fbd99/services/dask-sidecar/Dockerfile)
    return {
        "--dashboard-address": f":{OSPARC_SCHEDULER_DASHBOARD_PORT}",
        "--port": f"{OSPARC_SCHEDULER_API_PORT}",
        "--host": scheduler_service_name,
    }


def modify_cmd_argument(
    cmd: list[str], argument_name: str, argument_value: str
) -> list[str]:
    modified_cmd = deepcopy(cmd)
    try:
        dashboard_address_arg_index = modified_cmd.index(argument_name)
        modified_cmd[dashboard_address_arg_index + 1] = argument_value
    except ValueError:
        modified_cmd.extend([argument_name, argument_value])
    return modified_cmd


async def get_cluster_information(docker_client: Docker) -> ClusterInformation:
    cluster_information = cluster_information_from_docker_nodes(
        await docker_client.nodes.list()
    )

    return cluster_information


async def get_next_empty_node_hostname(
    docker_client: Docker, cluster: Cluster
) -> Hostname:
    current_count = getattr(get_next_empty_node_hostname, "counter", -1) + 1
    setattr(get_next_empty_node_hostname, "counter", current_count)

    cluster_nodes = deque(await docker_client.nodes.list())
    current_worker_services = await docker_client.services.list(
        filters={"label": [f"cluster_id={cluster.id}", "type=worker"]}
    )
    used_docker_node_ids = set()

    for service in current_worker_services:
        service_tasks = await docker_client.tasks.list(
            filters={"service": service["ID"]}
        )
        if not service_tasks:
            raise NoServiceTasksError(f"service {service} has no tasks attached")
        for task in service_tasks:
            if task["Status"]["State"] in ("new", "pending"):
                raise TaskNotAssignedError(f"task {task} is not assigned to a host yet")
            if task["Status"]["State"] in (
                "assigned",
                "preparing",
                "starting",
                "running",
            ):
                used_docker_node_ids.add(task["NodeID"])
    cluster_nodes.rotate(current_count)
    for node in cluster_nodes:
        if node["ID"] in used_docker_node_ids:
            continue
        return f"{node['Description']['Hostname']}"
    raise NoHostFoundError("Could not find any empty host")
