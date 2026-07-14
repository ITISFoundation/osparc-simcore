from typing import Final

from aws_library.ec2._models import AWSTagKey, AWSTagValue, EC2Tags
from pydantic import TypeAdapter

from ._meta import VERSION

_APPLICATION_TAG_PREFIX: Final[str] = "io.simcore.clusters-keeper"


DOCKER_STACK_DEPLOY_COMMAND_NAME: Final[str] = "private cluster docker deploy"
DOCKER_STACK_DEPLOY_COMMAND_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.private_cluster_docker_deploy"
)

CLUSTER_NAME_PREFIX: Final[str] = "osparc-computational-cluster-"

#
# EC2 tags
#
EC2_NAME_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("Name")
APPLICATION_VERSION_TAG: Final[EC2Tags] = TypeAdapter(EC2Tags).validate_python(
    {f"{_APPLICATION_TAG_PREFIX}.version": f"{VERSION}"}
)
EC2_MINIMAL_APPLICATION_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.deploy"
)
USER_ID_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("io.simcore.user_id")
PRODUCT_NAME_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("io.simcore.product_name")
WALLET_ID_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("io.simcore.wallet_id")
ROLE_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(f"{_APPLICATION_TAG_PREFIX}.role")
HEARTBEAT_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.last_heartbeat"
)

WORKER_ROLE_TAG_VALUE: Final[AWSTagValue] = TypeAdapter(AWSTagValue).validate_python("worker")
MANAGER_ROLE_TAG_VALUE: Final[AWSTagValue] = TypeAdapter(AWSTagValue).validate_python("manager")
