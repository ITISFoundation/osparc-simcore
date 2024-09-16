from typing import Final

from aws_library.ec2._models import AWSTagKey
from pydantic import parse_obj_as

DOCKER_STACK_DEPLOY_COMMAND_NAME: Final[str] = "private cluster docker deploy"
DOCKER_STACK_DEPLOY_COMMAND_EC2_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "io.simcore.clusters-keeper.private_cluster_docker_deploy"
)
