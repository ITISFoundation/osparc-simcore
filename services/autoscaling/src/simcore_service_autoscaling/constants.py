from pathlib import Path
from typing import Final

from aws_library.ec2._models import AWSTagKey, AWSTagValue, EC2Tags
from pydantic import PositiveInt, TypeAdapter

_APPLICATION_TAG_PREFIX: Final[str] = "io.simcore.autoscaling"


PREPULL_COMMAND_NAME: Final[str] = "docker images pulling"
DOCKER_COMPOSE_CMD: Final[str] = "docker compose"
PRE_PULL_COMPOSE_PATH: Final[Path] = Path("/docker-pull.compose.yml")
DOCKER_COMPOSE_PULL_SCRIPT_PATH: Final[Path] = Path("/docker-pull-script.sh")
DOCKER_PULL_COMMAND: Final[str] = f"{DOCKER_COMPOSE_CMD} -f {PRE_PULL_COMPOSE_PATH} -p buffering pull"

#
# EC2 boot scripts
#
# Printed before each boot step so cloud-init-output names the step that died
BOOT_STEP_MARKER_PREFIX: Final[str] = "simcore-boot"
# A machine that cannot log in to the registry retries this many times, one second apart, and fails its
# boot otherwise. It must not join the swarm in between: it would then be assigned services it cannot pull.
DOCKER_LOGIN_MAX_ATTEMPTS: Final[PositiveInt] = 3
DOCKER_LOGIN_ATTEMPT_TIMEOUT_S: Final[PositiveInt] = 20
# `timeout` sends SIGTERM at ATTEMPT_TIMEOUT_S and SIGKILL this many seconds later
DOCKER_LOGIN_KILL_DELAY_S: Final[PositiveInt] = 1
DOCKER_LOGIN_RETRY_DELAY_S: Final[PositiveInt] = 1

#
# EC2 tags
#
EC2_NAME_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("Name")
APPLICATION_VERSION_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.version"
)
APPLICATION_NODE_LABELS_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.monitored_nodes_labels"
)
APPLICATION_SERVICE_LABELS_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.monitored_services_labels"
)
APPLICATION_DASK_SCHEDULER_URL_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.dask-scheduler_url"
)
APPLICATION_CUSTOM_PLACEMENT_LABELS_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.ec2_instance.docker_node_labels"
)
INSTANCE_PULLING_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.pre-pulling-images"
)
INSTANCE_PULLING_COMMAND_ID_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.ssm-command-id"
)
INSTANCE_PRE_PULLED_IMAGES_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.pre_pulled_images"
)
WARM_BUFFER_MACHINE_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.warm_buffer_machine"
)
# NOTE: legacy tag key, kept only to recognize already-running EC2 instances tagged before the
# rename from '.buffer_machine' to '.warm_buffer_machine'. Remove once
# https://github.com/ITISFoundation/osparc-simcore/pull/9404 is in production and all warm
# buffer machines have cycled through with the new tag.
LEGACY_WARM_BUFFER_MACHINE_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.buffer_machine"
)
HOT_BUFFER_MACHINE_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    f"{_APPLICATION_TAG_PREFIX}.hot_buffer_machine"
)
HOT_BUFFER_MACHINE_EC2_TAGS: Final[EC2Tags] = {
    HOT_BUFFER_MACHINE_TAG_KEY: TypeAdapter(AWSTagValue).validate_python("true")
}
DEACTIVATED_BUFFER_MACHINE_EC2_TAGS: Final[EC2Tags] = {
    WARM_BUFFER_MACHINE_TAG_KEY: TypeAdapter(AWSTagValue).validate_python("true")
}
ACTIVATED_BUFFER_MACHINE_EC2_TAGS: Final[EC2Tags] = {
    WARM_BUFFER_MACHINE_TAG_KEY: TypeAdapter(AWSTagValue).validate_python("false")
}
# NOTE: legacy tag, see LEGACY_WARM_BUFFER_MACHINE_TAG_KEY above. Remove together with it.
LEGACY_DEACTIVATED_BUFFER_MACHINE_EC2_TAGS: Final[EC2Tags] = {
    LEGACY_WARM_BUFFER_MACHINE_TAG_KEY: TypeAdapter(AWSTagValue).validate_python("true")
}
