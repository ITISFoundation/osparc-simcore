""" Utils to deal with environment variables (environs in short)

"""
import re
from copy import deepcopy
from pathlib import Path
from typing import Dict

import yaml

VARIABLE_SUBSTITUTION = re.compile(r"\$\{(\w+)+")  #


def load_env(file_handler) -> Dict:
    """Deserializes an environment file like .env-devel and
    returns a key-value map of the environment

    Analogous to json.load
    """
    PATTERN_ENVIRON_EQUAL = re.compile(r"^(\w+)=(.*)$")
    # Works even for `POSTGRES_EXPORTER_DATA_SOURCE_NAME=postgresql://simcore:simcore@postgres:5432/simcoredb?sslmode=disable`

    environ = {}
    for line in file_handler:
        m = PATTERN_ENVIRON_EQUAL.match(line)
        if m:
            key, value = m.groups()
            environ[key] = str(value)
    return environ


def eval_environs_in_docker_compose(
    docker_compose: Dict,
    docker_compose_dir: Path,
    host_environ: Dict = None,
    *,
    use_env_devel=True
):
    """Resolves environments in docker compose and sets them under 'environment' section

    TODO: deprecated. Use instead docker-compose config in services/web/server/tests/integration/fixtures/docker_compose.py
    SEE https://docs.docker.com/compose/environment-variables/
    """
    content = deepcopy(docker_compose)
    for _name, service in content["services"].items():
        replace_environs_in_docker_compose_service(
            service, docker_compose_dir, host_environ, use_env_devel=use_env_devel
        )
    return content


def replace_environs_in_docker_compose_service(
    service_section: Dict,
    docker_compose_dir: Path,
    host_environ: Dict = None,
    *,
    use_env_devel=True
):
    """Resolves environments in docker-compose's service section,
    drops any reference to env_file and sets all
    environs 'environment' section

    NOTE: service_section gets modified!

    SEE https://docs.docker.com/compose/environment-variables/
    """
    service_environ = {}

    # environment defined in env_file
    env_files = service_section.pop("env_file", list())
    for env_file in env_files:
        if env_file == "../.env" and use_env_devel:
            env_file += "-devel"

        env_file_path = (docker_compose_dir / env_file).resolve()
        with env_file_path.open() as fh:
            file_environ = load_env(fh)
            service_environ.update(file_environ)

    # explicit environment [overrides env_file]
    environ_items = service_section.get("environment", list())
    if environ_items and isinstance(environ_items, list):
        # TODO: use docker-compose config first
        for item in environ_items:
            key, value = item.split("=")

            m = VARIABLE_SUBSTITUTION.match(value)
            if m:
                # In VAR=${FOO} matches VAR and FOO
                #    - TODO: add to read defaults
                envkey = m.groups()[0]
                value = host_environ[
                    envkey
                ]  # fails when variable in docker-compose is NOT defined
            service_environ[key] = value

    service_section["environment"] = service_environ


def eval_service_environ(
    docker_compose_path: Path,
    service_name: str,
    host_environ: Dict = None,
    image_environ: Dict = None,
    *,
    use_env_devel=True
) -> Dict:
    """Deduces a service environment with it runs in a stack from confirmation

    :param docker_compose_path: path to stack configuration
    :type docker_compose_path: Path
    :param service_name: service name as defined in docker-compose file
    :type service_name: str
    :param host_environ: environs in host when stack is started, defaults to None
    :type host_environ: Dict, optional
    :param image_environ: environs set in Dockerfile, defaults to None
    :type image_environ: Dict, optional
    :param image_environ: environs set in Dockerfile, defaults to None
    :rtype: Dict
    """
    docker_compose_dir = docker_compose_path.parent.resolve()
    with docker_compose_path.open() as f:
        content = yaml.safe_load(f)

    service = content["services"][service_name]
    replace_environs_in_docker_compose_service(
        service, docker_compose_dir, host_environ, use_env_devel=use_env_devel
    )

    host_environ = host_environ or {}
    image_environ = image_environ or {}

    # Environ expected in a running service
    service_environ = {}
    service_environ.update(image_environ)
    service_environ.update(service["environment"])
    return service_environ
