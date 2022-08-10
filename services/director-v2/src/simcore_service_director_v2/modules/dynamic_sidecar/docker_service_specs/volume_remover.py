import json
from asyncio.log import logger
from uuid import uuid4

from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.services_resources import (
    CPU_10_PERCENT,
    CPU_100_PERCENT,
    MEMORY_50MB,
    MEMORY_250MB,
)

from ....models.schemas.constants import DYNAMIC_VOLUME_REMOVER_PREFIX


# NOTE: below `retry` function is inspired by
# https://gist.github.com/sj26/88e1c6584397bb7c13bd11108a579746
SH_SCRIPT_REMOVE_VOLUMES = """
set -e;

error_counter=0

function retry {{
  local retries={retries}
  shift

  local count=0
  until "$@"; do
    exit=$?

    count=$(($count + 1))
    if [ $count -lt $retries ]; then
      echo "Retry $count/$retries exited $exit, retrying in {sleep} seconds..."
      sleep {sleep}
    else
      echo "Retry $count/$retries exited $exit, no more retries left."
      let error_counter=error_counter+1
      return 0
    fi
  done
  return 0
}}

for volume_name in {volume_names_seq}
do
    retry 3 docker volume rm "$volume_name"
done

if [ "$error_counter" -ne "0" ]; then
    echo "ERROR: Please check above logs, there was/were $error_counter error/s."
    exit 1
fi
"""


def spec_volume_removal_service(
    docker_node_id: str,
    volume_names: list[str],
    docker_version: str,
    *,
    volume_removal_attempts: int,
    sleep_between_attempts_s: int,
) -> AioDockerServiceSpec:
    """
    Starts service `docker:{docker_version}-dind` to the:
    above bash script which for each volume name attempts
    to remove it by retrying a few times

    NOTE: expect the container to exit with code 0,
    otherwise there was an error.
    NOTE: the bash script will exit 1 if it cannot find a
    volume to remove.
    NOTE: service must be removed once it finishes or it will
    remain in the system.
    """

    # computing timeouts based on the attempts required to remove

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
