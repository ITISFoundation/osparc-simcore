# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import re
import shutil
import socket
import subprocess
import sys
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Dict

import pytest
import yaml


@pytest.fixture("session")
def devel_environ(env_devel_file) -> Dict[str, str]:
    """ Loads and extends .env-devel

    """
    PATTERN_ENVIRON_EQUAL= re.compile(r"^(\w+)=(.*)$")
    env_devel = {}
    with env_devel_file.open() as f:
        for line in f:
            m = PATTERN_ENVIRON_EQUAL.match(line)
            if m:
                key, value = m.groups()
                env_devel[key] = str(value)

    # Customized EXTENSION: change some of the environ to accomodate the test case ----
    if 'REGISTRY_SSL' in env_devel:
        env_devel['REGISTRY_SSL'] = 'False'
    if 'REGISTRY_URL' in env_devel:
        env_devel['REGISTRY_URL'] = "{}:5000".format(_get_ip())
    if 'REGISTRY_USER' in env_devel:
        env_devel['REGISTRY_USER'] = "simcore"
    if 'REGISTRY_PW' in env_devel:
        env_devel['REGISTRY_PW'] = ""
    if 'REGISTRY_AUTH' in env_devel:
        env_devel['REGISTRY_AUTH'] = False
    return env_devel

@pytest.fixture(scope="module")
def temp_folder(request, tmpdir_factory) -> Path:
    tmp = Path(tmpdir_factory.mktemp("docker_compose_{}".format(request.module.__name__)))
    yield tmp


@pytest.fixture("module")
def osparc_simcore_docker_compose_all(osparc_simcore_root_dir, devel_environ, temp_folder):
    """ Runs config on full docker-compose stack and resolves paths, environs, etc

    """
    destination_path = temp_folder / "docker-compose-all.yml"
    try:
        # composes list
        docker_compose_paths = [ osparc_simcore_root_dir / "services" / file_name
            for file_name in [
                "docker-compose.yml",
                "docker-compose-tools.yml"]
            ]

        assert all([p.exists() for p in docker_compose_paths])

        options = " ".join('-f "{}"'.format(os.path.relpath(docker_compose_path, osparc_simcore_root_dir))
            for docker_compose_path in docker_compose_paths )

        # ensures .env at git_root_dir
        env_path = osparc_simcore_root_dir / ".env"
        backup_path = osparc_simcore_root_dir / ".env-bak"
        if env_path.exists():
            shutil.copy(env_path, backup_path)

        with env_path.open('wt') as fh:
            print(f"# TEMPORARY .env auto-generated from env_path in {__file__}")
            for key, value in devel_environ.items():
                print(f"{key}={value}", file=fh)

        # TODO: use instead python api of docker-compose!
        cmd = f"docker-compose {options} config > {destination_path}"
        process = subprocess.run(
                cmd,
                shell=True, check=True,
                cwd=osparc_simcore_root_dir
            )
        assert process.returncode == 0, "Error in '{}'. Typically service dependencies missing. Check stdout/err for more details.".format(cmd)

    finally:
        env_path.unlink()
        if backup_path.exists():
            shutil.copy(backup_path, env_path)
            backup_path.unlink()

    content = {}
    # docker-compose config resolves nicely paths and environs, etc
    with destination_path.open() as f:
        content = yaml.safe_load(f)
    return content


@pytest.fixture("module")
def services_docker_compose(osparc_simcore_root_dir, osparc_simcore_docker_compose_all) -> Dict[str, str]:
    """ Filters only services in services/docker-compose.yml

    """
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.yml"
    assert docker_compose_path.exists()

    content = _filter_docker_compose(docker_compose_path, osparc_simcore_docker_compose_all)
    return content


@pytest.fixture("module")
def tools_docker_compose(osparc_simcore_root_dir, osparc_simcore_docker_compose_all) -> Dict[str, str]:
    """ Filters only services in docker-compose-tools.yml

    """
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose-tools.yml"
    assert docker_compose_path.exists()

    content = _filter_docker_compose(docker_compose_path, osparc_simcore_docker_compose_all)
    return content


@pytest.fixture(scope='module')
def docker_compose_file(request, temp_folder, services_docker_compose):
    """ Creates a docker-compose.yml with services listed in 'core_services' module variable
        File is created in a temp folder

        Overrides pytest-docker fixture
    """
    core_services = getattr(request.module, 'core_services', []) # TODO: PC->SAN could also be defined as a fixture (as with docker_compose)
    docker_compose_path = Path(temp_folder / 'docker-compose.core_services.yml')

    _filter_services_and_dump(core_services, services_docker_compose, docker_compose_path)

    yield docker_compose_path

    # cleanup if not failed
    docker_compose_path.unlink()


@pytest.fixture(scope='module')
def tools_docker_compose_file(request, temp_folder, tools_docker_compose):
    """ Creates a docker-compose.yml with services listed in 'tool_services' module variable
        File is created in a temp folder
    """
    tool_services = getattr(request.module, 'tool_services', [])
    docker_compose_path = Path(temp_folder / 'docker-compose.tool_services.yml')

    _filter_services_and_dump(tool_services, tools_docker_compose, docker_compose_path)

    yield docker_compose_path

    # cleanup TODO: if not failed
    docker_compose_path.unlink()

# HELPERS ---------------------------------------------
def _get_ip()->str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception: #pylint: disable=W0703
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def _filter_docker_compose(docker_compose_path: Path, complete_docker_compose: Dict ):
    # find which sections to include
    include = defaultdict(list)
    with docker_compose_path.open() as f:
        content = yaml.safe_load(f)

        for key, section in content.items():
            if isinstance(section, dict):
                include[key] = list(section.keys())
    filtered_section = [k for k in complete_docker_compose if k in include]

    # delete everything except these sections
    content = deepcopy(complete_docker_compose)
    for section in filtered_section:
        for key in complete_docker_compose[section]:
            if key not in include[section]:
                content[section].pop(key)

    return content

def _filter_services_and_dump(include, services_compose, docker_compose_path):
    content = deepcopy(services_compose)

    # filters services
    remove = [name for name in content['services'] if name not in include]
    for name in remove:
        content['services'].pop(name, None)

    for name in include:
        service = content['services'][name]
        # removes builds (No more)
        if "build" in service:
            service.pop("build", None)


    # updates current docker-compose (also versioned ... do not change by hand)
    with docker_compose_path.open('wt') as f:
        yaml.dump(content, f, default_flow_style=False)

    # resolves
    subprocess.run(f"docker-compose -f {docker_compose_path.name} config > {docker_compose_path.name}",
        shell=True, check=True, cwd=docker_compose_path.parent)

    # shows
    with docker_compose_path.open('r') as f:
        print("{:-^30}".format(str(docker_compose_path)))
        print("-"*30)
        print(f.read())
