import logging
import os
import socket
import subprocess
import tempfile
from pathlib import Path
from pprint import pformat
from typing import Dict, List, Optional, Union

import docker
import yaml
from tenacity import after_log, retry, stop_after_attempt, wait_fixed

log = logging.getLogger(__name__)


def get_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(("10.255.255.255", 1))
        IP = s.getsockname()[0]
    except Exception:  # pylint: disable=W0703
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP


@retry(
    wait=wait_fixed(2), stop=stop_after_attempt(10), after=after_log(log, logging.WARN)
)
def get_service_published_port(
    service_name: str, target_ports: Optional[Union[List[int], int]] = None
) -> str:
    # WARNING: ENSURE that service name exposes a port in
    # Dockerfile file or docker-compose config file

    # NOTE: retries since services can take some time to start
    client = docker.from_env()

    services = [x for x in client.services.list() if str(x.name).endswith(service_name)]
    if not services:
        raise RuntimeError(
            f"Cannot find published port for service '{service_name}'."
            "Probably services still not started."
        )

    service_ports = services[0].attrs["Endpoint"].get("Ports")
    if not service_ports:
        raise RuntimeError(
            f"Cannot find published port for service '{service_name}' in endpoint."
            "Probably services still not started."
        )

    published_port = None
    msg = ", ".join(
        f"{p.get('TargetPort')} -> {p.get('PublishedPort')}" for p in service_ports
    )

    if target_ports is None:
        if len(service_ports) > 1:
            log.warning(
                "Multiple ports published in service '%s': %s. Defaulting to first",
                service_name,
                msg,
            )
        published_port = service_ports[0]["PublishedPort"]

    else:
        ports_to_look_for: List = (
            [target_ports] if isinstance(target_ports, (int, str)) else target_ports
        )

        for target_port in ports_to_look_for:
            target_port = int(target_port)
            for p in service_ports:
                if p["TargetPort"] == target_port:
                    published_port = p["PublishedPort"]
                    break

    if published_port is None:
        raise RuntimeError(f"Cannot find published port for {target_ports}. Got {msg}")

    return str(published_port)


def run_docker_compose_config(
    docker_compose_paths: Union[List[Path], Path],
    workdir: Path,
    destination_path: Path,
    env_file_path: Optional[Path] = None,
) -> Dict:
    """Runs docker-compose config to validate and resolve a compose file configuration

    - Composes all configurations passed in 'docker_compose_paths'
    - Takes 'workdir' as current working directory (i.e. all '.env' files there will be captured)
    - Saves resolved output config to 'destination_path' (if given)
    """
    # TODO: test

    if not isinstance(docker_compose_paths, List):
        docker_compose_paths = [
            docker_compose_paths,
        ]

    if destination_path.suffix not in [".yml", ".yaml"]:
        raise ValueError("Expected yaml/yml file as destination path")

    # SEE https://docs.docker.com/compose/reference/
    # SEE https://docs.docker.com/compose/reference/config/

    config_paths = [
        f"--file {os.path.relpath(docker_compose_path, workdir)}"
        for docker_compose_path in docker_compose_paths
    ]
    configs_prefix = " ".join(config_paths)

    # Environment
    if env_file_path:
        # Specifies custom environment variables
        #
        # SEE https://docs.docker.com/compose/env-file/
        configs_prefix += f" --env-file {env_file_path}"
        # NOTE: subprocess inherits the current process environment variables as well

    # TODO: should be args a string or list??
    # https://stackoverflow.com/questions/15109665/subprocess-call-using-string-vs-using-list
    subprocess.run(
        f"docker-compose {configs_prefix} config > {destination_path}",
        shell=True,
        check=True,
        cwd=workdir,
    )

    #
    # NOTE: This step could be avoided and reading instead from stdout
    # but prefer to have a file that stays after the test in a tmp folder
    # and can be used later for debugging
    #
    with destination_path.open() as f:
        config = yaml.safe_load(f)

    return config


def save_docker_infos(destination_path: Path):
    client = docker.from_env()
    all_containers = client.containers.list()
    # ensure the parent dir exists
    destination_path.mkdir(parents=True, exist_ok=True)
    # get the services logs
    for cont in all_containers:
        service_file = destination_path / f"{cont.name}.logs"
        service_file.write_text(
            pformat(
                cont.logs(timestamps=True, stdout=True, stderr=True).decode(), width=200
            ),
        )
    print("\n\twrote docker log files in ", destination_path)
