from typing import Final

from aws_library.ec2._models import AWSTagKey, AWSTagValue
from pydantic import parse_obj_as

DOCKER_STACK_DEPLOY_COMMAND_NAME: Final[str] = "private cluster docker deploy"
DOCKER_STACK_DEPLOY_COMMAND_EC2_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "io.simcore.clusters-keeper.private_cluster_docker_deploy"
)

USER_ID_TAG_KEY: Final[AWSTagKey] = parse_obj_as(AWSTagKey, "user_id")
WALLET_ID_TAG_KEY: Final[AWSTagKey] = parse_obj_as(AWSTagKey, "wallet_id")
ROLE_TAG_KEY: Final[AWSTagKey] = parse_obj_as(AWSTagKey, "role")
WORKER_ROLE_TAG_VALUE: Final[AWSTagValue] = parse_obj_as(AWSTagValue, "worker")
MANAGER_ROLE_TAG_VALUE: Final[AWSTagValue] = parse_obj_as(AWSTagValue, "manager")
