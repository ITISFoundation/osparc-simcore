from aws_library.ec2._models import AWSTagKey, EC2Tags
from models_library.docker import DockerGenericTag
from pydantic import TypeAdapter

from ..constants import PRE_PULLED_IMAGES_EC2_TAG_KEY
from .utils_ec2 import (
    dump_as_ec2_tags,
    list_tag_keys,
    load_from_ec2_tags,
)


def dump_pre_pulled_images_as_tags(images: list[DockerGenericTag]) -> EC2Tags:
    """Serialize pre-pulled images to EC2 tags with automatic chunking.

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
    return list_tag_keys(tags, base_tag_key=PRE_PULLED_IMAGES_EC2_TAG_KEY)
