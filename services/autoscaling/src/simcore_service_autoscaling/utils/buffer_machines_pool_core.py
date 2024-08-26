from typing import Final, Iterable

from aws_library.ec2 import AWSTagKey, AWSTagValue, EC2Tags
from fastapi import FastAPI
from models_library.docker import DockerGenericTag
from pydantic import parse_obj_as

from ..modules.auto_scaling_mode_base import BaseAutoscaling

_BUFFER_MACHINE_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "io.simcore.autoscaling.buffer_machine"
)
_DEACTIVATED_BUFFER_MACHINE_EC2_TAGS: Final[EC2Tags] = {
    _BUFFER_MACHINE_TAG_KEY: parse_obj_as(AWSTagValue, "true")
}
_ACTIVATED_BUFFER_MACHINE_EC2_TAGS: Final[EC2Tags] = {
    _BUFFER_MACHINE_TAG_KEY: parse_obj_as(AWSTagValue, "false")
}


def get_activated_buffer_ec2_tags(
    app: FastAPI, auto_scaling_mode: BaseAutoscaling
) -> EC2Tags:
    return auto_scaling_mode.get_ec2_tags(app) | _ACTIVATED_BUFFER_MACHINE_EC2_TAGS


def get_deactivated_buffer_ec2_tags(
    app: FastAPI, auto_scaling_mode: BaseAutoscaling
) -> EC2Tags:
    base_ec2_tags = (
        auto_scaling_mode.get_ec2_tags(app) | _DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    )
    base_ec2_tags[AWSTagKey("Name")] = AWSTagValue(
        f"{base_ec2_tags[AWSTagKey('Name')]}-buffer"
    )
    return base_ec2_tags


def is_buffer_machine(tags: EC2Tags) -> bool:
    return bool(_BUFFER_MACHINE_TAG_KEY in tags)


def dump_pre_pulled_images_as_tags(images: Iterable[DockerGenericTag]) -> EC2Tags:
    # AWS Tag Values are limited to 256 characaters so we chunk the images
    # into smaller chunks
    ...


def load_pre_pulled_images_from_tags(tags: EC2Tags) -> tuple[DockerGenericTag]:
    # AWS Tag values are limited to 256 characters so we chunk the images
    ...
