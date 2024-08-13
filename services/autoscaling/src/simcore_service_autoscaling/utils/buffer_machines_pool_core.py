from typing import Final

from aws_library.ec2 import AWSTagKey, AWSTagValue, EC2Tags
from fastapi import FastAPI
from pydantic import parse_obj_as

from ..modules.auto_scaling_mode_base import BaseAutoscaling

BUFFER_MACHINE_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "io.simcore.autoscaling.buffer_machine"
)
_BUFFER_MACHINE_EC2_TAGS: EC2Tags = {
    BUFFER_MACHINE_TAG_KEY: parse_obj_as(AWSTagValue, "true")
}


def get_buffer_ec2_tags(app: FastAPI, auto_scaling_mode: BaseAutoscaling) -> EC2Tags:
    base_ec2_tags = auto_scaling_mode.get_ec2_tags(app) | _BUFFER_MACHINE_EC2_TAGS
    base_ec2_tags[AWSTagKey("Name")] = AWSTagValue(
        f"{base_ec2_tags[AWSTagKey('Name')]}-buffer"
    )
    return base_ec2_tags
