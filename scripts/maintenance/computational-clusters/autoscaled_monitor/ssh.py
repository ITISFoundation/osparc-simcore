import contextlib
from pathlib import Path
from typing import Any, Final, Generator

from paramiko import Ed25519Key
from sshtunnel import SSHTunnelForwarder

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
