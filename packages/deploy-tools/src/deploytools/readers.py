""" File readers

"""

from typing import Dict, Optional

import yaml

from .utils import env_devel_file, osparc_simcore_root_dir


def load_docker_compose(suffix: Optional[str]=None) -> Dict:
    name = "docker-compose"
    if suffix:
        name += suffix
    name += ".yml"
    dcpath = osparc_simcore_root_dir() / "services" / name
    assert dcpath.exists(), dcpath

    dc = dict()
    with dcpath.open() as f:
        dc = yaml.safe_load(f)
    return dc


def load_devel_environ(name: Optional[str]=None):
    environ = {}
    with env_devel_file(name).open() as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=")
                environ[key] = value
    return environ
