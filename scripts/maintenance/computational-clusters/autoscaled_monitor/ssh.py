import contextlib
import datetime
import json
import logging
import re
import select
import socketserver
import threading
from collections import defaultdict
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any, Final

import arrow
import paramiko
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


@contextlib.contextmanager
def ssh_tunnel(
    *,
    ssh_host: str,
    username: str,
    private_key_path: Path,
    remote_bind_host: str,
    remote_bind_port: int,
) -> Generator[tuple[str, int], Any]:
    """
    Create a local port forwarding tunnel through a bastion/jump host using paramiko.

    This context manager:
    1. Establishes SSH connection to the bastion host
    2. Binds a local port (127.0.0.1:0) that forwards to the remote host/port
    3. Yields the (host, port) tuple for the local endpoint
    4. Cleans up the tunnel when the context exits

    Args:
        ssh_host: Bastion host to connect through
        username: SSH username for bastion authentication
        private_key_path: Path to SSH private key
        remote_bind_host: Target host behind the bastion (e.g., private IP)
        remote_bind_port: Target port on the remote host

    Yields:
        Tuple of (local_host, local_port) that forwards to the remote endpoint
    """

    # Multi-threaded TCP server that can handle concurrent connections
    class _ForwardServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    # Request handler that proxies data between local socket and remote channel
    class _Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            try:
                # Open a direct-tcpip channel through the bastion to the target host
                chan = transport.open_channel(  # type: ignore[attr-defined]
                    "direct-tcpip",
                    (remote_bind_host, remote_bind_port),
                    self.request.getsockname(),
                )
            except Exception:  # pragma: no cover - network dependent
                _logger.exception("Failed to open channel through bastion host")
                return

            # Bidirectional proxy: forward data between local socket and SSH channel
            try:
                while True:
                    # Wait for data from either the local socket or remote channel
                    readable, _, _ = select.select([self.request, chan], [], [])

                    # Forward data from local client to remote host
                    if self.request in readable:
                        data = self.request.recv(1024)
                        if not data:
                            break
                        chan.sendall(data)

                    # Forward data from remote host to local client
                    if chan in readable:
                        data = chan.recv(1024)
                        if not data:
                            break
                        self.request.sendall(data)
            finally:
                chan.close()
                self.request.close()

    try:
        # Establish SSH connection to the bastion host
        with paramiko.SSHClient() as client:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                ssh_host,
                _DEFAULT_SSH_PORT,
                username=username,
                key_filename=f"{private_key_path}",
                timeout=5,
            )

            # Get the transport layer and enable keepalive to maintain connection
            transport = client.get_transport()
            assert transport  # nosec
            transport.set_keepalive(10)

            # Create local server bound to 127.0.0.1:0 (OS assigns free port)
            server = _ForwardServer((_LOCAL_BIND_ADDRESS, 0), _Handler)

            # Run the server in a background thread
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()

            try:
                # Yield the local (host, port) that clients should connect to
                yield server.server_address
            finally:
                # Clean up: stop server and wait for thread to finish
                server.shutdown()
                server.server_close()
                server_thread.join()
    except Exception:
        _logger.exception("Unexpected issue with ssh tunnel")
        raise


@contextlib.contextmanager
def _ssh_client(
    hostname: str, port: int, *, username: str, private_key_path: Path
) -> Generator[paramiko.SSHClient, Any]:
    try:
        with paramiko.SSHClient() as client:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname,
                port,
                username=username,
                key_filename=f"{private_key_path}",
                timeout=5,
            )
            yield client
    except Exception:
        _logger.exception("Unexpected issue with ssh client")
        raise
    finally:
        pass


@contextlib.asynccontextmanager
async def ssh_instance(
    instance: Instance, *, state: AppState, username: str, private_key_path: Path
) -> AsyncGenerator[paramiko.SSHClient, Any]:
    """ssh in instance with/without tunnel as needed"""
    assert state.ssh_key_path  # nosec
    try:
        async with contextlib.AsyncExitStack() as stack:
            if instance.public_ip_address:
                hostname = instance.public_ip_address
                port = _DEFAULT_SSH_PORT
            else:
                assert state.environment
                bastion_instance = await get_bastion_instance_from_remote_instance(state, instance)
                tunnel = stack.enter_context(
                    ssh_tunnel(
                        ssh_host=bastion_instance.public_dns_name,
                        username=username,
                        private_key_path=state.ssh_key_path,
                        remote_bind_host=instance.private_ip_address,
                        remote_bind_port=_DEFAULT_SSH_PORT,
                    )
                )
                hostname, port = tunnel
            ssh_client = stack.enter_context(
                _ssh_client(
                    hostname,
                    port,
                    username=username,
                    private_key_path=private_key_path,
                )
            )
            yield ssh_client

    finally:
        pass


async def get_available_disk_space(
    state: AppState, instance: Instance, username: str, private_key_path: Path
) -> ByteSize:
    assert state.ssh_key_path

    try:
        async with ssh_instance(
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
            return ByteSize(available_space if available_space else 0)
    except (
        paramiko.AuthenticationException,
        paramiko.SSHException,
        TimeoutError,
    ):
        return ByteSize(0)


async def get_dask_ip(state: AppState, instance: Instance, username: str, private_key_path: Path) -> str:
    try:
        async with ssh_instance(
            instance, state=state, username=username, private_key_path=private_key_path
        ) as ssh_client:
            # First, get the container IDs for dask-sidecar or dask-scheduler
            list_containers_command = "docker ps --filter 'name=dask-sidecar|dask-scheduler' --format '{{.ID}}'"
            _, stdout, stderr = ssh_client.exec_command(list_containers_command)
            container_ids = stdout.read().decode("utf-8").strip()
            exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0 or not container_ids:
                error_message = stderr.read().decode().strip()
                _logger.warning(
                    "No matching containers found or command failed with exit status %s: %s",
                    exit_status,
                    error_message,
                )
                return "No Containers Found / Not Ready"

            # If containers are found, inspect their IP addresses
            dask_ip_command = (
                f"docker inspect -f '{{{{.NetworkSettings.Networks.dask_stack_cluster.IPAddress}}}}' {container_ids}"
            )
            _, stdout, stderr = ssh_client.exec_command(dask_ip_command)
            exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0:
                error_message = stderr.read().decode().strip()
                _logger.error(
                    "Inspecting Dask IP command failed with exit status %s: %s",
                    exit_status,
                    error_message,
                )
                return "Not docker network Found / Drained / Not Ready"

            ip_address = stdout.read().decode("utf-8").strip()
            if not ip_address:
                _logger.error("Dask IP address not found in the output")
                return "Not IP Found / Drained / Not Ready"

            return ip_address
    except (
        paramiko.AuthenticationException,
        paramiko.SSHException,
        TimeoutError,
    ):
        return "Not Ready"


async def list_running_dyn_services(
    state: AppState, instance: Instance, username: str, private_key_path: Path
) -> list[DynamicService]:
    try:
        async with ssh_instance(
            instance, state=state, username=username, private_key_path=private_key_path
        ) as ssh_client:
            # Run the Docker command to list containers
            _stdin, stdout, stderr = ssh_client.exec_command(
                'docker ps --format=\'{{.Names}}\t{{.CreatedAt}}\t{{.Label "io.simcore.runtime.user-id"}}\t{{.Label "io.simcore.runtime.project-id"}}\t{{.Label "io.simcore.name"}}\t{{.Label "io.simcore.version"}}\t{{.Label "io.simcore.runtime.product-name"}}\t{{.Label "io.simcore.runtime.simcore-user-agent"}}\' --filter=name=dy-',  # noqa: E501
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
                            tzinfo=datetime.UTC,
                        ).datetime,
                        container,
                        (json.loads(match["service_name"])["name"] if match["service_name"] else ""),
                        (json.loads(match["service_version"])["version"] if match["service_version"] else ""),
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
        paramiko.AuthenticationException,
        paramiko.SSHException,
        TimeoutError,
    ):
        return []
