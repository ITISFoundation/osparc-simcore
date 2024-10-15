import re
from typing import Final

from aws_library.ec2._models import AWSTagKey, AWSTagValue, EC2Tags
from pydantic import TypeAdapter

BUFFER_MACHINE_PULLING_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("pulling")
BUFFER_MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("ssm-command-id")
PREPULL_COMMAND_NAME: Final[str] = "docker images pulling"

DOCKER_JOIN_COMMAND_NAME: Final[str] = "docker swarm join"
DOCKER_JOIN_COMMAND_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("io.simcore.autoscaling.joined_command_sent")


DOCKER_PULL_COMMAND: Final[
    str
] = "docker compose -f /docker-pull.compose.yml -p buffering pull"

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
PRE_PULLED_IMAGES_RE: Final[re.Pattern] = re.compile(
    rf"{PRE_PULLED_IMAGES_EC2_TAG_KEY}_(\((\d+)\)|\d+)"
)
