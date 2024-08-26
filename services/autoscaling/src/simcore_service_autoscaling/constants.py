from typing import Final

from aws_library.ec2._models import AWSTagKey
from pydantic import parse_obj_as

BUFFER_MACHINE_PULLING_EC2_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "pulling"
)
BUFFER_MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "ssm-command-id"
)
PREPULL_COMMAND_NAME: Final[str] = "docker images pulling"

DOCKER_PULL_COMMAND: Final[
    str
] = "docker compose -f /docker-pull.compose.yml -p buffering pull"

PRE_PULLED_IMAGES_EC2_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "io.simcore.autoscaling.pre_pulled_images"
)
