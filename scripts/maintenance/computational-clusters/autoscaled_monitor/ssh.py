import contextlib
import datetime
import logging
import re
from collections import defaultdict
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Final

import arrow
import asyncssh
import orjson
import rich
import typer
from mypy_boto3_ec2.service_resource import Instance
from pydantic import ByteSize

from .constants import DYN_SERVICES_NAMING_CONVENTION
from .ec2 import get_bastion_instance_from_remote_instance
from .models import AppState, DockerContainer, DynamicService

_DEFAULT_SSH_PORT: Final[int] = 22
_LOCAL_BIND_ADDRESS: Final[str] = "127.0.0.1"

_logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def ssh_tunnel(
    *,
    ssh_host: str,
    username: str,
    private_key_path: Path,
    remote_bind_host: str,
    remote_bind_port: int,
) -> AsyncGenerator[tuple[str, int], Any]:
    """Open an asyncssh TCP port-forward and yield (local_host, local_port)."""
    try:
        async with asyncssh.connect(
            ssh_host,
            port=_DEFAULT_SSH_PORT,
            username=username,
            client_keys=[str(private_key_path)],
            known_hosts=None,
            keepalive_interval=10,
        ) as conn:
            listener = await conn.forward_local_port(_LOCAL_BIND_ADDRESS, 0, remote_bind_host, remote_bind_port)
            try:
                yield (_LOCAL_BIND_ADDRESS, listener.get_port())
            finally:
                listener.close()
                await listener.wait_closed()
    except TimeoutError:
        _logger.warning("Timeout while establishing ssh tunnel")
    except Exception:
        _logger.exception("Unexpected issue with ssh tunnel")
        raise


@contextlib.asynccontextmanager
async def ssh_instance(
    instance: Instance, *, state: AppState, username: str, private_key_path: Path
) -> AsyncGenerator[asyncssh.SSHClientConnection, Any]:
    """SSH into an instance, tunnelling through the bastion when needed."""
    assert state.ssh_key_path  # nosec
    try:
        if instance.public_ip_address:
            async with asyncssh.connect(
                instance.public_ip_address,
                port=_DEFAULT_SSH_PORT,
                username=username,
                client_keys=[str(private_key_path)],
                known_hosts=None,
            ) as conn:
                yield conn
        else:
            bastion_instance = await get_bastion_instance_from_remote_instance(state, instance)
            async with (
                asyncssh.connect(
                    bastion_instance.public_dns_name,
                    port=_DEFAULT_SSH_PORT,
                    username=username,
                    client_keys=[str(state.ssh_key_path)],
                    known_hosts=None,
                    keepalive_interval=10,
                ) as bastion_conn,
                bastion_conn.connect_ssh(
                    instance.private_ip_address,
                    port=_DEFAULT_SSH_PORT,
                    username=username,
                    client_keys=[str(private_key_path)],
                    known_hosts=None,
                ) as conn,
            ):
                yield conn
    except (asyncssh.Error, OSError):
        _logger.warning("Could not connect to ssh instance %s", instance.id)
        raise


async def _run_command(conn: asyncssh.SSHClientConnection, command: str) -> asyncssh.SSHCompletedProcess:
    return await conn.run(command, check=False, timeout=10)


async def get_available_disk_space(
    state: AppState, instance: Instance, username: str, private_key_path: Path
) -> ByteSize:
    assert state.ssh_key_path

    try:
        async with ssh_instance(instance, state=state, username=username, private_key_path=private_key_path) as conn:
            disk_space_command = "df --block-size=1 /mnt/docker | awk 'NR==2{print $4}'"
            result = await _run_command(conn, disk_space_command)

            if result.exit_status != 0:
                rich.print(result.stderr)
                raise typer.Abort(result.stderr)

            available_space = (result.stdout or "").strip()
            return ByteSize(available_space if available_space else 0)
    except (
        asyncssh.Error,
        OSError,
        TimeoutError,
    ):
        return ByteSize(0)


async def get_dask_ip(state: AppState, instance: Instance, username: str, private_key_path: Path) -> str:
    try:
        async with ssh_instance(instance, state=state, username=username, private_key_path=private_key_path) as conn:
            list_containers_command = "docker ps --filter 'name=dask-sidecar|dask-scheduler' --format '{{.ID}}'"
            result = await _run_command(conn, list_containers_command)
            container_ids = (result.stdout or "").strip()

            if result.exit_status != 0 or not container_ids:
                error_message = (result.stderr or "").strip()
                _logger.warning(
                    "No matching containers found or command failed with exit status %s: %s",
                    result.exit_status,
                    error_message,
                )
                return "No Containers Found / Not Ready"

            dask_ip_command = (
                f"docker inspect -f '{{{{.NetworkSettings.Networks.dask_stack_cluster.IPAddress}}}}' {container_ids}"
            )
            result = await _run_command(conn, dask_ip_command)

            if result.exit_status != 0:
                error_message = (result.stderr or "").strip()
                _logger.error(
                    "Inspecting Dask IP command failed with exit status %s: %s",
                    result.exit_status,
                    error_message,
                )
                return "Not docker network Found / Drained / Not Ready"

            ip_address = (result.stdout or "").strip()
            if not ip_address:
                _logger.error("Dask IP address not found in the output")
                return "Not IP Found / Drained / Not Ready"

            return ip_address
    except (
        asyncssh.Error,
        OSError,
        TimeoutError,
    ):
        return "Not Ready"


async def list_running_dyn_services(
    state: AppState, instance: Instance, username: str, private_key_path: Path
) -> list[DynamicService]:
    try:
        async with ssh_instance(instance, state=state, username=username, private_key_path=private_key_path) as conn:
            docker_command = (
                'docker ps --format=\'{{.Names}}\t{{.CreatedAt}}\t{{.Label "io.simcore.runtime.user-id"}}'
                '\t{{.Label "io.simcore.runtime.project-id"}}\t{{.Label "io.simcore.name"}}'
                '\t{{.Label "io.simcore.version"}}\t{{.Label "io.simcore.runtime.product-name"}}'
                '\t{{.Label "io.simcore.runtime.simcore-user-agent"}}\' --filter=name=dy-'
            )
            result = await _run_command(conn, docker_command)

            if result.exit_status != 0:
                rich.print(result.stderr)
                raise typer.Abort(result.stderr)

            output = result.stdout or ""
            running_service: dict[str, list[DockerContainer]] = defaultdict(list)
            for container in output.splitlines():
                if match := re.match(DYN_SERVICES_NAMING_CONVENTION, container):
                    named_container = DockerContainer(
                        match["node_id"],
                        int(match["user_id"]),
                        match["project_id"],
                        arrow.get(
                            match["created_at"],
                            "YYYY-MM-DD HH:mm:ss",
                            tzinfo=datetime.UTC,
                        ).datetime,
                        container,
                        (orjson.loads(match["service_name"])["name"] if match["service_name"] else ""),
                        (orjson.loads(match["service_version"])["version"] if match["service_version"] else ""),
                        match["product_name"],
                        match["simcore_user_agent"],
                    )
                    running_service[match["node_id"]].append(named_container)

            def _needs_manual_intervention(
                running_containers: list[DockerContainer],
            ) -> bool:
                valid_prefixes = ["dy-sidecar_", "dy-proxy_", "dy-sidecar-"]
                for prefix in valid_prefixes:
                    found = any(container.name.startswith(prefix) for container in running_containers)
                    if not found:
                        return True
                return False

            return [
                DynamicService(
                    node_id=node_id,
                    user_id=containers[0].user_id,
                    project_id=containers[0].project_id,
                    created_at=containers[0].created_at,
                    needs_manual_intervention=_needs_manual_intervention(containers)
                    and ((arrow.utcnow().datetime - containers[0].created_at) > datetime.timedelta(minutes=2)),
                    containers=[c.name for c in containers],
                    service_name=containers[0].service_name,
                    service_version=containers[0].service_version,
                    product_name=containers[0].product_name,
                    simcore_user_agent=containers[0].simcore_user_agent,
                )
                for node_id, containers in running_service.items()
            ]
    except (
        asyncssh.Error,
        OSError,
        TimeoutError,
    ):
        return []
