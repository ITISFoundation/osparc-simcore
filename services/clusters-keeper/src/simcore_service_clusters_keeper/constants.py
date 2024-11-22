from typing import Final

from aws_library.ec2._models import AWSTagKey, AWSTagValue
from pydantic import TypeAdapter

DOCKER_STACK_DEPLOY_COMMAND_NAME: Final[str] = "private cluster docker deploy"
DOCKER_STACK_DEPLOY_COMMAND_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("io.simcore.clusters-keeper.private_cluster_docker_deploy")

USER_ID_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("user_id")
WALLET_ID_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    "wallet_id"
)
ROLE_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("role")
WORKER_ROLE_TAG_VALUE: Final[AWSTagValue] = TypeAdapter(AWSTagValue).validate_python(
    "worker"
)
MANAGER_ROLE_TAG_VALUE: Final[AWSTagValue] = TypeAdapter(AWSTagValue).validate_python(
    "manager"
)
