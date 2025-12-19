from pathlib import Path
from typing import Final

from aws_library.ec2._models import AWSTagKey, AWSTagValue, EC2Tags
from pydantic import TypeAdapter

MACHINE_PULLING_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    "pulling"
)
MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("ssm-command-id")
PREPULL_COMMAND_NAME: Final[str] = "docker images pulling"

DOCKER_JOIN_COMMAND_NAME: Final[str] = "docker swarm join"
DOCKER_JOIN_COMMAND_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("io.simcore.autoscaling.joined_command_sent")

DOCKER_COMPOSE_CMD: Final[str] = "docker compose"
PRE_PULL_COMPOSE_PATH: Final[Path] = Path("/docker-pull.compose.yml")
DOCKER_COMPOSE_PULL_SCRIPT_PATH: Final[Path] = Path("/docker-pull-script.sh")


DOCKER_PULL_COMMAND: Final[str] = (
    f"{DOCKER_COMPOSE_CMD} -f {PRE_PULL_COMPOSE_PATH} -p buffering pull"
)

PRE_PULLED_IMAGES_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("io.simcore.autoscaling.pre_pulled_images")

BUFFER_MACHINE_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    "io.simcore.autoscaling.buffer_machine"
)
DEACTIVATED_BUFFER_MACHINE_EC2_TAGS: Final[EC2Tags] = {
    BUFFER_MACHINE_TAG_KEY: TypeAdapter(AWSTagValue).validate_python("true")
}
ACTIVATED_BUFFER_MACHINE_EC2_TAGS: Final[EC2Tags] = {
    BUFFER_MACHINE_TAG_KEY: TypeAdapter(AWSTagValue).validate_python("false")
}
