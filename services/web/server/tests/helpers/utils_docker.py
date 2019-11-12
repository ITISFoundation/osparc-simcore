
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union

import docker
import yaml
from tenacity import after_log, retry, stop_after_attempt, wait_fixed

log = logging.getLogger(__name__)

@retry(
    wait=wait_fixed(2),
    stop=stop_after_attempt(10),
    after=after_log(log, logging.WARN))
def get_service_published_port(service_name: str) -> str:
    # WARNING: ENSURE that service name defines a port
    # NOTE: retries since services can take some time to start
    client = docker.from_env()
    services = [x for x in client.services.list() if service_name in x.name]
    if not services:
        raise RuntimeError("Cannot find published port for service '%s'. Probably services still not up" % service_name)
    service_endpoint = services[0].attrs["Endpoint"]

    if "Ports" not in service_endpoint or not service_endpoint["Ports"]:
        raise RuntimeError("Cannot find published port for service '%s' in endpoint. Probably services still not up" % service_name)

    published_port = service_endpoint["Ports"][0]["PublishedPort"]
    return str(published_port)


def run_docker_compose_config(
    docker_compose_paths: Union[List[Path], Path],
    workdir: Path,
    destination_path: Optional[Path]=None) -> Dict:
    """ Runs docker-compose config to validate and resolve a compose file configuration

        - Composes all configurations passed in 'docker_compose_paths'
        - Takes 'workdir' as current working directory (i.e. all '.env' files there will be captured)
        - Saves resolved output config to 'destination_path' (if given)
    """

    if not isinstance(docker_compose_paths, List):
        docker_compose_paths = [docker_compose_paths, ]

    temp_dir = None
    if destination_path is None:
        temp_dir = Path(tempfile.mkdtemp(prefix=''))
        destination_path = temp_dir / 'docker-compose.yml'

    config_paths = [ f"-f {os.path.relpath(docker_compose_path, workdir)}" for docker_compose_path in docker_compose_paths]
    configs_prefix = " ".join(config_paths)

    # TODO: use instead python api of docker-compose!
    subprocess.run( f"docker-compose {configs_prefix} config > {destination_path}",
        shell=True, check=True,
        cwd=workdir)

    with destination_path.open() as f:
        config = yaml.safe_load(f)

    if temp_dir:
        temp_dir.unlink()

    return config
