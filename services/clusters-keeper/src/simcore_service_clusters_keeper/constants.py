from typing import Final

from aws_library.ec2._models import AWSTagKey, AWSTagValue, EC2Tags
from pydantic import TypeAdapter

from ._meta import VERSION

_APPLICATION_TAG_KEY: Final[str] = "io.simcore.clusters-keeper"


DOCKER_STACK_DEPLOY_COMMAND_NAME: Final[str] = "private cluster docker deploy"
DOCKER_STACK_DEPLOY_COMMAND_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_KEY}.private_cluster_docker_deploy"
)


APPLICATION_VERSION_TAG_KEY: Final[EC2Tags] = TypeAdapter(EC2Tags).validate_python(
    {f"{_APPLICATION_TAG_KEY}.version": f"{VERSION}"}
)
EC2_MINIMAL_APPLICATION_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_KEY}.deploy"
)
EC2_NAME_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("Name")
USER_ID_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("io.simcore.user_id")
PRODUCT_NAME_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("io.simcore.product_name")
WALLET_ID_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("io.simcore.wallet_id")
ROLE_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(f"{_APPLICATION_TAG_KEY}.role")
HEARTBEAT_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(f"{_APPLICATION_TAG_KEY}.last_heartbeat")

WORKER_ROLE_TAG_VALUE: Final[AWSTagValue] = TypeAdapter(AWSTagValue).validate_python("worker")
MANAGER_ROLE_TAG_VALUE: Final[AWSTagValue] = TypeAdapter(AWSTagValue).validate_python("manager")


CLUSTER_NAME_PREFIX: Final[str] = "osparc-computational-cluster-"
