from typing import Final

from aws_library.ec2 import AWSTagKey, AWSTagValue, EC2Tags
from aws_library.ec2._models import EC2InstanceBootSpecific
from models_library.docker import DockerGenericTag
from pydantic import TypeAdapter

from ..constants import (
    ACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    BUFFER_MACHINE_TAG_KEY,
    DEACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    PRE_PULLED_IMAGES_EC2_TAG_KEY,
)
from ..core.settings import ApplicationSettings
from . import utils_docker
from .utils_ec2 import (
    dump_as_ec2_tags,
    list_chunked_tag_keys,
    load_from_ec2_tags,
)

_NAME_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("Name")


def get_activated_warm_buffer_ec2_tags(base_ec2_tags: EC2Tags) -> EC2Tags:
    return base_ec2_tags | ACTIVATED_BUFFER_MACHINE_EC2_TAGS


def get_deactivated_warm_buffer_ec2_tags(base_ec2_tags: EC2Tags) -> EC2Tags:
    new_base_ec2_tags = base_ec2_tags | DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    new_base_ec2_tags[_NAME_EC2_TAG_KEY] = TypeAdapter(AWSTagValue).validate_python(
        f"{new_base_ec2_tags[_NAME_EC2_TAG_KEY]}-buffer"
    )
    return new_base_ec2_tags


def is_warm_buffer_machine(tags: EC2Tags) -> bool:
    return bool(BUFFER_MACHINE_TAG_KEY in tags)


def dump_pre_pulled_images_as_tags(images: list[DockerGenericTag]) -> EC2Tags:
    """Serialize pre-pulled images to EC2 tags with automatic chunking.

    Uses generic chunking utility to handle AWS tag size limits transparently.

    Args:
        images: List of Docker image tags to serialize

    Returns:
        EC2Tags dict with either single or chunked tags
    """
    return dump_as_ec2_tags(images, base_tag_key=PRE_PULLED_IMAGES_EC2_TAG_KEY)


def load_pre_pulled_images_from_tags(tags: EC2Tags) -> list[DockerGenericTag]:
    """Deserialize pre-pulled images from EC2 tags.

    Handles both single tag and chunked tag formats.
    Returns sorted list of images, or empty list if no tags found.

    Args:
        tags: EC2Tags dict to load from

    Returns:
        Sorted list of Docker image tags

    Raises:
        Ec2TagDeserializationError: If tag data is malformed
    """
    images = load_from_ec2_tags(
        tags,
        base_tag_key=PRE_PULLED_IMAGES_EC2_TAG_KEY,
        type_adapter=TypeAdapter(list[DockerGenericTag]),
    )
    return sorted(images) if images is not None else []


def list_pre_pulled_images_tag_keys(tags: EC2Tags) -> list[AWSTagKey]:
    """List all EC2 tag keys related to pre-pulled images.

    Identifies both single and chunked tag formats.

    Args:
        tags: EC2Tags dict to search

    Returns:
        List of matching tag keys
    """
    return list_chunked_tag_keys(tags, base_tag_key=PRE_PULLED_IMAGES_EC2_TAG_KEY)


def ec2_warm_buffer_startup_script(
    ec2_boot_specific: EC2InstanceBootSpecific, app_settings: ApplicationSettings
) -> str:
    startup_commands = ec2_boot_specific.custom_boot_scripts.copy()
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    desired_pre_pull_images = utils_docker.compute_full_list_of_pre_pulled_images(
        ec2_boot_specific, app_settings
    )
    if desired_pre_pull_images:
        assert app_settings.AUTOSCALING_REGISTRY  # nosec

        startup_commands.extend(
            (
                utils_docker.get_docker_login_on_start_bash_command(
                    app_settings.AUTOSCALING_REGISTRY
                ),
                utils_docker.write_compose_file_command(desired_pre_pull_images),
            )
        )
    return " && ".join(startup_commands)
