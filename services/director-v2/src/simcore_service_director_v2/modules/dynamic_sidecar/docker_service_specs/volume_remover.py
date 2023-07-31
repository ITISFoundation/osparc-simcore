import json
import re
from asyncio.log import logger
from typing import Final
from uuid import uuid4

from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_resources import (
    CPU_10_PERCENT,
    CPU_100_PERCENT,
    MEMORY_50MB,
    MEMORY_250MB,
)
from models_library.users import UserID
from pydantic import parse_obj_as
from simcore_service_director_v2.constants import DYNAMIC_VOLUME_REMOVER_PREFIX

from ....core.settings import DynamicSidecarSettings


class DockerVersion(str):
    """
    Extracts `XX.XX.XX` where X is a range [0-9] from
    a given docker version
    """

    @classmethod
    def __get_validators__(cls):
        yield cls.validate_docker_version

    @classmethod
    def validate_docker_version(cls, docker_version: str) -> str:
        try:
            search_result = re.search(r"^\d\d.(\d\d|\d).(\d\d|\d)", docker_version)
            assert search_result  # nosec
            return search_result.group()
        except AttributeError:
            raise ValueError(  # pylint: disable=raise-missing-from
                f"{docker_version} appears not to be a valid docker version"
            )


DIND_VERSION: Final[DockerVersion] = parse_obj_as(DockerVersion, "20.10.14")

# NOTE: below `retry` function is inspired by
# https://gist.github.com/sj26/88e1c6584397bb7c13bd11108a579746
SH_SCRIPT_REMOVE_VOLUMES = """
set -e;

error_counter=0

function retry {{
  local retries=$1
  shift

  local count=0
  while true;
  do

    local command_result
    set +e
    $($@ > /tmp/command_result 2>&1)
    exit_code=$?
    set -e

    command_result=$(cat /tmp/command_result)
    echo "$command_result"
    volume_name=$4

    case "$command_result" in
      *"Error: No such volume: $volume_name"*)
        return 0
        ;;
    esac

    if [ $exit_code -eq 0 ]; then
        return 0
    fi

    count=$(($count + 1))
    if [ $count -lt $retries ]; then
      echo "Retry $count/$retries exited $exit_code, retrying in {sleep} seconds..."
      sleep {sleep}
    else
      echo "Retry $count/$retries exited $exit_code, no more retries left."
      let error_counter=error_counter+1
      return 0
    fi
  done
  return 0
}}

for volume_name in {volume_names_seq}
do
    retry {retries} docker volume rm "$volume_name"
done

if [ "$error_counter" -ne "0" ]; then
    echo "ERROR: Please check above logs, there was/were $error_counter error/s."
    exit 1
fi
"""


def spec_volume_removal_service(
    dynamic_sidecar_settings: DynamicSidecarSettings,
    docker_node_id: str,
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    volume_names: list[str],
    docker_version: DockerVersion = DIND_VERSION,
    *,
    volume_removal_attempts: int,
    sleep_between_attempts_s: int,
    service_timeout_s: int,
) -> AioDockerServiceSpec:
    """
    Generates a service spec for with base image
    `docker:{docker_version}-dind` running the above bash script.

    The bash script will attempt to remove each individual volume
    a few times before giving up.
    The script will exit with error if it is not capable of
    removing the volume.

    NOTE: expect the container of the service to exit with code 0,
    otherwise there was an error.
    NOTE: the bash script will exit 1 if it cannot find a
    volume to remove.
    NOTE: service must be removed once it finishes or it will
    remain in the system.
    NOTE: when running docker-in-docker https://hub.docker.com/_/docker
    selecting the same version as the actual docker engine running
    on the current node allows to avoid possible incompatible
    versions. It is assumed that the same version of docker
    will be running in the entire swarm.
    """

    volume_names_seq = " ".join(volume_names)
    formatted_command = SH_SCRIPT_REMOVE_VOLUMES.format(
        volume_names_seq=volume_names_seq,
        retries=volume_removal_attempts,
        sleep=sleep_between_attempts_s,
    )
    logger.debug("Service will run:\n%s", formatted_command)
    command = ["sh", "-c", formatted_command]

    create_service_params = {
        "labels": {
            "volume_names": json.dumps(volume_names),
            "volume_removal_attempts": f"{volume_removal_attempts}",
            "sleep_between_attempts_s": f"{sleep_between_attempts_s}",
            "service_timeout_s": f"{service_timeout_s}",
            "swarm_stack_name": dynamic_sidecar_settings.SWARM_STACK_NAME,
            "user_id": f"{user_id}",
            "study_id": f"{project_id}",
            "node_id": f"{node_uuid}",
        },
        "name": f"{DYNAMIC_VOLUME_REMOVER_PREFIX}_{uuid4()}",
        "task_template": {
            "ContainerSpec": {
                "Command": command,
                "Image": f"docker:{docker_version}-dind",
                "Mounts": [
                    {
                        "Source": "/var/run/docker.sock",
                        "Target": "/var/run/docker.sock",
                        "Type": "bind",
                    }
                ],
            },
            "Placement": {"Constraints": [f"node.id == {docker_node_id}"]},
            "RestartPolicy": {"Condition": "none"},
            "Resources": {
                "Reservations": {
                    "MemoryBytes": MEMORY_50MB,
                    "NanoCPUs": CPU_10_PERCENT,
                },
                "Limits": {"MemoryBytes": MEMORY_250MB, "NanoCPUs": CPU_100_PERCENT},
            },
        },
    }
    return AioDockerServiceSpec.parse_obj(create_service_params)
