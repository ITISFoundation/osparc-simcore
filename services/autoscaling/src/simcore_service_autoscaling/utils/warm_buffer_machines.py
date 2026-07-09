import asyncio
import logging

from aws_library.ec2 import AWSTagValue, EC2InstanceData, EC2Tags, SimcoreEC2API
from aws_library.ec2._models import EC2InstanceBootSpecific
from pydantic import TypeAdapter
from types_aiobotocore_ec2.literals import InstanceStateNameType

from ..constants import (
    ACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    DEACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    EC2_NAME_TAG_KEY,
    LEGACY_DEACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    LEGACY_WARM_BUFFER_MACHINE_TAG_KEY,
    WARM_BUFFER_MACHINE_TAG_KEY,
)
from ..core.settings import ApplicationSettings
from . import utils_docker

_logger = logging.getLogger(__name__)


def get_activated_warm_buffer_ec2_tags(base_ec2_tags: EC2Tags) -> EC2Tags:
    return base_ec2_tags | ACTIVATED_BUFFER_MACHINE_EC2_TAGS


def get_deactivated_warm_buffer_ec2_tags(base_ec2_tags: EC2Tags) -> EC2Tags:
    new_base_ec2_tags = base_ec2_tags | DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    new_base_ec2_tags[EC2_NAME_TAG_KEY] = TypeAdapter(AWSTagValue).validate_python(
        f"{new_base_ec2_tags[EC2_NAME_TAG_KEY]}-buffer"
    )
    return new_base_ec2_tags


def get_legacy_deactivated_warm_buffer_ec2_tags(base_ec2_tags: EC2Tags) -> EC2Tags:
    """Returns the EC2 tags for a legacy deactivated warm buffer machine.
    Remove once https://github.com/ITISFoundation/osparc-simcore/pull/9404
    is in production and all warm buffer machines have cycled through with the new tag.

    Arguments:
        base_ec2_tags -- The base EC2 tags of the instance.

    Returns:
        The updated EC2 tags including the legacy deactivated warm buffer machine tags.
    """
    new_base_ec2_tags = base_ec2_tags | LEGACY_DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    new_base_ec2_tags[EC2_NAME_TAG_KEY] = TypeAdapter(AWSTagValue).validate_python(
        f"{new_base_ec2_tags[EC2_NAME_TAG_KEY]}-buffer"
    )
    return new_base_ec2_tags


async def get_warm_buffer_ec2_instances(
    ec2_client: SimcoreEC2API,
    *,
    key_names: list[str],
    base_ec2_tags: EC2Tags,
    state_names: list[InstanceStateNameType] | None = None,
) -> list[EC2InstanceData]:
    """Fetches deactivated warm buffer EC2 instances, including those still tagged with the
    deprecated legacy tag key for backward compatibility during the tag migration.
    Cleanup once https://github.com/ITISFoundation/osparc-simcore/pull/9404 is
    in production and all warm buffer machines have cycled through with the new tag."""
    instances, legacy_instances = await asyncio.gather(
        ec2_client.get_instances(
            key_names=key_names,
            tags=get_deactivated_warm_buffer_ec2_tags(base_ec2_tags),
            state_names=state_names,
        ),
        ec2_client.get_instances(
            key_names=key_names,
            tags=get_legacy_deactivated_warm_buffer_ec2_tags(base_ec2_tags),
            state_names=state_names,
        ),
    )
    if legacy_instances:
        _logger.warning(
            "Found %s warm buffer machine(s) still tagged with the deprecated '%s' tag: %s. "
            "This fallback will be removed once "
            "https://github.com/ITISFoundation/osparc-simcore/pull/9404 is in production and all "
            "warm buffer machines have cycled through with the new '%s' tag.",
            len(legacy_instances),
            LEGACY_WARM_BUFFER_MACHINE_TAG_KEY,
            [i.id for i in legacy_instances],
            WARM_BUFFER_MACHINE_TAG_KEY,
        )
    known_ids = {i.id for i in instances}
    return instances + [i for i in legacy_instances if i.id not in known_ids]


def is_warm_buffer_machine(tags: EC2Tags) -> bool:
    return bool(WARM_BUFFER_MACHINE_TAG_KEY in tags or LEGACY_WARM_BUFFER_MACHINE_TAG_KEY in tags)


def ec2_warm_buffer_startup_script(
    ec2_boot_specific: EC2InstanceBootSpecific, app_settings: ApplicationSettings
) -> str:
    startup_commands = ec2_boot_specific.custom_boot_scripts.copy()
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    desired_pre_pull_images = utils_docker.compute_full_list_of_pre_pulled_images(ec2_boot_specific, app_settings)
    if desired_pre_pull_images:
        assert app_settings.AUTOSCALING_REGISTRY  # nosec

        startup_commands.extend(
            (
                utils_docker.get_docker_login_on_start_bash_command(app_settings.AUTOSCALING_REGISTRY),
                utils_docker.write_compose_file_command(desired_pre_pull_images),
            )
        )
    return " && ".join(startup_commands)
