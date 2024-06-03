import contextlib
import datetime
import json
import re
from collections import defaultdict
from collections.abc import Generator
from pathlib import Path
from typing import Any, Final

import arrow
import paramiko
import rich
import typer
from mypy_boto3_ec2.service_resource import Instance
from paramiko import Ed25519Key
from pydantic import AnyUrl, ByteSize
from sshtunnel import SSHTunnelForwarder

from .constants import DYN_SERVICES_NAMING_CONVENTION
from .models import AppState, DockerContainer, DynamicService
from .utils import to_async

_DEFAULT_SSH_PORT: Final[int] = 22
_LOCAL_BIND_ADDRESS: Final[str] = "127.0.0.1"


@contextlib.contextmanager
def ssh_tunnel(
    *,
    ssh_host: str,
    username: str,
    private_key_path: Path,
    remote_bind_host: str,
    remote_bind_port: int,
) -> Generator[SSHTunnelForwarder | None, Any, None]:
    try:
        with SSHTunnelForwarder(
            (ssh_host, _DEFAULT_SSH_PORT),
            ssh_username=username,
            ssh_pkey=Ed25519Key(filename=private_key_path),
            remote_bind_address=(remote_bind_host, remote_bind_port),
            local_bind_address=(_LOCAL_BIND_ADDRESS, 0),
            set_keepalive=10,
        ) as tunnel:
            yield tunnel
    finally:
        pass


@contextlib.contextmanager
def _ssh_client(
    url: AnyUrl, *, username: str, private_key_path: Path
) -> Generator[paramiko.SSHClient, Any, None]:
    try:
        with paramiko.SSHClient() as client:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                f"{url}",
                username=username,
                key_filename=f"{private_key_path}",
                timeout=5,
            )
            yield client

    finally:
        pass


@contextlib.contextmanager
def ssh_instance(
    instance: Instance, *, state: AppState, username: str, private_key_path: Path
) -> Generator[paramiko.SSHClient, Any, None]:
    """ssh in instance with/without tunnel as needed"""
    assert state.ssh_key_path  # nosec
    try:
        with contextlib.ExitStack() as stack:
            url = AnyUrl(instance.public_ip_address)
            if state.use_bastion:
                assert state.environment
                tunnel = stack.enter_context(
                    ssh_tunnel(
                        ssh_host="123.12.321.21",
                        username=username,
                        private_key_path=state.ssh_key_path,
                        remote_bind_host=instance.private_ip_address,
                        remote_bind_port=_DEFAULT_SSH_PORT,
                    )
                )
                assert tunnel  # nosec
                host, port = tunnel.local_bind_address
                url = AnyUrl(f"{host}:{port}")

                ssh_client = stack.enter_context(
                    _ssh_client(
                        url, username=username, private_key_path=private_key_path
                    )
                )
                yield ssh_client
    finally:
        pass


@to_async
def get_available_disk_space(
    state: AppState, instance: Instance, username: str, private_key_path: Path
) -> ByteSize:
    assert state.ssh_key_path

    try:
        with ssh_instance(
            instance, state=state, username=username, private_key_path=private_key_path
        ) as ssh_client:
            # Command to get disk space for /docker partition
            disk_space_command = "df --block-size=1 /mnt/docker | awk 'NR==2{print $4}'"

            # Run the command on the remote machine
            _, stdout, stderr = ssh_client.exec_command(disk_space_command)
            exit_status = stdout.channel.recv_exit_status()
            error = stderr.read().decode()

            if exit_status != 0:
                rich.print(error)
                raise typer.Abort(error)

            # Available disk space will be captured here
            available_space = stdout.read().decode("utf-8").strip()
            return ByteSize(available_space)
    except (
        paramiko.AuthenticationException,
        paramiko.SSHException,
        TimeoutError,
    ):
        return ByteSize(0)


@to_async
def get_dask_ip(
    state: AppState, instance: Instance, username: str, private_key_path: Path
) -> str:

    try:
        with ssh_instance(
            instance, state=state, username=username, private_key_path=private_key_path
        ) as ssh_client:
            dask_ip_command = "docker inspect -f '{{.NetworkSettings.Networks.dask_stack_default.IPAddress}}' $(docker ps --filter 'name=dask-sidecar|dask-scheduler' --format '{{.ID}}')"

            # Run the command on the remote machine
            _, stdout, _ = ssh_client.exec_command(dask_ip_command)
            exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0:
                return "Not Found / Drained / Not Ready"

            # Available disk space will be captured here
            return stdout.read().decode("utf-8").strip()
    except (
        paramiko.AuthenticationException,
        paramiko.SSHException,
        TimeoutError,
    ):
        return "Not Ready"


@to_async
def list_running_dyn_services(
    state: AppState, instance: Instance, username: str, private_key_path: Path
) -> list[DynamicService]:
    try:
        with ssh_instance(
            instance, state=state, username=username, private_key_path=private_key_path
        ) as ssh_client:
            # Run the Docker command to list containers
            _stdin, stdout, stderr = ssh_client.exec_command(
                'docker ps --format=\'{{.Names}}\t{{.CreatedAt}}\t{{.Label "io.simcore.runtime.user-id"}}\t{{.Label "io.simcore.runtime.project-id"}}\t{{.Label "io.simcore.name"}}\t{{.Label "io.simcore.version"}}\' --filter=name=dy-',
            )
            exit_status = stdout.channel.recv_exit_status()
            error = stderr.read().decode()
            if exit_status != 0:
                rich.print(error)
                raise typer.Abort(error)

            output = stdout.read().decode("utf-8")
            # Extract containers that follow the naming convention
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
                            tzinfo=datetime.timezone.utc,
                        ).datetime,
                        container,
                        (
                            json.loads(match["service_name"])["name"]
                            if match["service_name"]
                            else ""
                        ),
                        (
                            json.loads(match["service_version"])["version"]
                            if match["service_version"]
                            else ""
                        ),
                    )
                    running_service[match["node_id"]].append(named_container)

            def _needs_manual_intervention(
                running_containers: list[DockerContainer],
            ) -> bool:
                valid_prefixes = ["dy-sidecar_", "dy-proxy_", "dy-sidecar-"]
                for prefix in valid_prefixes:
                    found = any(
                        container.name.startswith(prefix)
                        for container in running_containers
                    )
                    if not found:
                        return True
                return False

            return [
                DynamicService(
                    node_id=node_id,
                    user_id=containers[0].user_id,
                    project_id=containers[0].project_id,
                    created_at=containers[0].created_at,
                    needs_manual_intervention=_needs_manual_intervention(containers),
                    containers=[c.name for c in containers],
                    service_name=containers[0].service_name,
                    service_version=containers[0].service_version,
                )
                for node_id, containers in running_service.items()
            ]
    except (
        paramiko.AuthenticationException,
        paramiko.SSHException,
        TimeoutError,
    ):
        return []
