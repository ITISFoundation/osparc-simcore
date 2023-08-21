import json
import logging
import os
import re
import socket
import subprocess
from enum import Enum
from pathlib import Path
from typing import Any

import docker
import yaml
from tenacity import retry
from tenacity.after import after_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed


# NOTE: CANNOT use models_library.generated_models.docker_rest_api.Status2 because some of the
# packages tests installations do not include this library!!
class ContainerStatus(str, Enum):
    """
    String representation of the container state. Can be one of "created",
    "running", "paused", "restarting", "removing", "exited", or "dead".

    """

    # SEE https://docs.docker.com/engine/api/v1.42/#tag/Container/operation/ContainerList

    created = "created"
    running = "running"
    paused = "paused"
    restarting = "restarting"
    removing = "removing"
    exited = "exited"
    dead = "dead"


_COLOR_ENCODING_RE = re.compile(r"\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[mGK]")
_MAX_PATH_CHAR_LEN_ALLOWED = 260
_kFILENAME_TOO_LONG = 36
_NORMPATH_COUNT = 0


log = logging.getLogger(__name__)


def get_localhost_ip(default="127.0.0.1") -> str:
    """Return the IP address for localhost"""
    local_ip = default
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(("10.255.255.255", 1))
        local_ip = s.getsockname()[0]
    finally:
        s.close()
    return f"{local_ip}"


@retry(
    wait=wait_fixed(2),
    stop=stop_after_attempt(10),
    after=after_log(log, logging.WARNING),
)
def get_service_published_port(
    service_name: str, target_ports: list[int] | int | None = None
) -> str:
    # WARNING: ENSURE that service name exposes a port in
    # Dockerfile file or docker-compose config file

    # NOTE: retries since services can take some time to start
    client = docker.from_env()

    services = [s for s in client.services.list() if str(s.name).endswith(service_name)]
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
        ports_to_look_for: list = (
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
    docker_compose_paths: list[Path] | Path,
    scripts_dir: Path,
    project_dir: Path,
    env_file_path: Path,
    destination_path: Path | None = None,
) -> dict:
    """Runs docker compose config to validate and resolve a compose file configuration

    - Composes all configurations passed in 'docker_compose_paths'
    - Takes 'project_dir' as current working directory to resolve relative paths in the docker-compose correctly
    - All environments are interpolated from a custom env-file at 'env_file_path'
    - Saves resolved output config to 'destination_path' (if given)
    """

    if not isinstance(docker_compose_paths, list):
        docker_compose_paths = [
            docker_compose_paths,
        ]

    assert project_dir.exists(), "Invalid file '{project_dir}'"

    for docker_compose_path in docker_compose_paths:
        assert str(docker_compose_path.resolve()).startswith(str(project_dir.resolve()))

    assert env_file_path.exists(), "Invalid file '{env_file_path}'"

    if destination_path:
        assert destination_path.suffix in [
            ".yml",
            ".yaml",
        ], "Expected yaml/yml file as destination path"

    # SEE https://docs.docker.com/compose/reference/

    global_options = [
        "-p",
        str(project_dir),  # Specify an alternate working directory
    ]
    # https://docs.docker.com/compose/environment-variables/#using-the---env-file--option
    global_options += [
        "-e",
        str(env_file_path),  # Custom environment variables
    ]

    # Specify an alternate compose files
    #  - When you use multiple Compose files, all paths in the files are relative to the first configuration file specified with -f.
    #    You can use the --project-directory option to override this base path.
    for docker_compose_path in docker_compose_paths:
        global_options += [os.path.relpath(docker_compose_path, project_dir)]

    # SEE https://docs.docker.com/compose/reference/config/
    docker_compose_path = scripts_dir / "docker" / "docker-compose-config.bash"
    assert docker_compose_path.exists()

    cmd = [f"{docker_compose_path}"] + global_options
    print(" ".join(cmd))

    process = subprocess.run(
        cmd,
        shell=False,
        check=True,
        cwd=project_dir,
        stdout=subprocess.PIPE,
    )

    compose_file_str = process.stdout.decode("utf-8")
    compose_file: dict[str, Any] = yaml.safe_load(compose_file_str)

    def _remove_top_level_name_attribute_generated_by_compose_v2(
        compose: dict[str, Any]
    ) -> dict[str, Any]:
        """docker compose V2 CLI config adds a top level name attribute
        https://docs.docker.com/compose/compose-file/#name-top-level-element
        but it is incompatible with docker stack deploy...
        """
        compose.pop("name", None)
        return compose

    compose_file = _remove_top_level_name_attribute_generated_by_compose_v2(
        compose_file
    )

    if destination_path:
        #
        # NOTE: This step could be avoided and reading instead from stdout
        # but prefer to have a file that stays after the test in a tmp folder
        # and can be used later for debugging
        #
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(compose_file_str)

    return compose_file


def shorten_path(filename: str) -> Path:
    # These paths are composed using test name hierarchies
    # when the test is parametrized, it uses the str of the
    # object as id which could result in path that goes over
    # allowed limit (260 characters).
    # This helper function tries to normalize the path
    # Another possibility would be that the path has some
    # problematic characters but so far we did not find any case ...
    global _NORMPATH_COUNT  # pylint: disable=global-statement

    if len(filename) > _MAX_PATH_CHAR_LEN_ALLOWED:
        _NORMPATH_COUNT += 1
        path = Path(filename)
        if path.is_dir():
            limit = _MAX_PATH_CHAR_LEN_ALLOWED - 60
            filename = filename[:limit] + f"{_NORMPATH_COUNT}"
        elif path.is_file():
            limit = _MAX_PATH_CHAR_LEN_ALLOWED - 10
            filename = filename[:limit] + f"{_NORMPATH_COUNT}{path.suffix}"

    return Path(filename)


# actions/upload-artifact@v2:
#    Invalid characters for artifact paths include:
#      Double quote ", Colon :, Less than <, Greater than >, Vertical bar |, Asterisk *,
#      Question mark ?, Carriage return \r, Line feed \n
BANNED_CHARS_FOR_ARTIFACTS = re.compile(r'["\:><|\*\?]')


def safe_artifact_name(name: str) -> str:
    return BANNED_CHARS_FOR_ARTIFACTS.sub("_", name)


def save_docker_infos(destination_dir: Path):
    client = docker.from_env()

    # Includes stop containers, which might be e.g. failing tasks
    all_containers = client.containers.list(all=True)

    destination_dir = Path(safe_artifact_name(f"{destination_dir}"))

    if all_containers:
        try:
            destination_dir.mkdir(parents=True, exist_ok=True)

        except OSError as err:
            if err.errno == _kFILENAME_TOO_LONG:
                destination_dir = shorten_path(err.filename)
                destination_dir.mkdir(parents=True, exist_ok=True)

        for container in all_containers:
            try:
                container_name = safe_artifact_name(container.name)

                # logs w/o coloring characters
                logs: str = container.logs(timestamps=True, tail=1000).decode()

                try:
                    (destination_dir / f"{container_name}.log").write_text(
                        _COLOR_ENCODING_RE.sub("", logs)
                    )

                except OSError as err:
                    if err.errno == _kFILENAME_TOO_LONG:
                        shorten_path(err.filename).write_text(
                            _COLOR_ENCODING_RE.sub("", logs)
                        )

                # inspect attrs
                try:
                    (destination_dir / f"{container_name}.json").write_text(
                        json.dumps(container.attrs, indent=2)
                    )
                except OSError as err:
                    if err.errno == _kFILENAME_TOO_LONG:
                        shorten_path(err.filename).write_text(
                            json.dumps(container.attrs, indent=2)
                        )

            except Exception as err:  # pylint: disable=broad-except
                if container.status != ContainerStatus.created:
                    print(
                        f"Error while dumping {container.name=}, {container.status=}.\n\t{err=}"
                    )

        print(
            "\n\t",
            f"wrote docker log and json files for {len(all_containers)} containers in ",
            destination_dir,
        )
