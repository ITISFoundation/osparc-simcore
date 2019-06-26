from typing import Dict




def load_environment(file_handler) -> Dict:
    """
        Loads a file like .env-devel and produces a key-value map
    """
    environ = {}
    for line in file_handler:
        line = line.strip()
        if line and not line.startswith("#"):
            key, value = line.split("=")
            environ[key] = value
    return environ

from pathlib import Path

import yaml
import re

VARIABLE_PATTERN = re.compile(r'\$\{(\w+)+')

def load_service_environment(docker_compose_path:Path, service_name:str, host_environ: Dict=None, image_environ: Dict=None) -> Dict:

    docker_compose_dir = docker_compose_path.parent.resolve()
    with docker_compose_path.open() as f:
        dc = yaml.safe_load(f)

    service = dc["services"][service_name]

    host_environ = host_environ or {}
    image_environ = image_environ or {}

    # Environ expected in a running service
    service_environ = {}
    service_environ.update(image_environ)

    # environment defined in env_file
    for env_file in service.get("env_file", list()):
        env_file_path = (docker_compose_dir / env_file).resolve()
        with env_file_path.open() as fh:
            file_environ = load_environment(fh)
            service_environ.update(file_environ)

    # explicit environment [overrides env_file]
    environ_items = service["environment"]
    for item in environ_items:
        key, value = item.split("=")
        m = VARIABLE_PATTERN.match(value)
        if m:
            envkey = m.groups()[0]
            value = host_environ[envkey]
        service_environ[key] = value

    return service_environ
