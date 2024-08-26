from collections.abc import Iterable
from operator import itemgetter

from aws_library.ec2 import AWSTagKey, AWSTagValue, EC2Tags
from fastapi import FastAPI
from models_library.docker import DockerGenericTag
from models_library.utils.json_serialization import json_dumps, json_loads
from pydantic import parse_obj_as, parse_raw_as

from ..constants import (
    ACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    BUFFER_MACHINE_TAG_KEY,
    DEACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    PRE_PULLED_IMAGES_EC2_TAG_KEY,
    PRE_PULLED_IMAGES_RE,
)
from ..modules.auto_scaling_mode_base import BaseAutoscaling


def get_activated_buffer_ec2_tags(
    app: FastAPI, auto_scaling_mode: BaseAutoscaling
) -> EC2Tags:
    return auto_scaling_mode.get_ec2_tags(app) | ACTIVATED_BUFFER_MACHINE_EC2_TAGS


def get_deactivated_buffer_ec2_tags(
    app: FastAPI, auto_scaling_mode: BaseAutoscaling
) -> EC2Tags:
    base_ec2_tags = (
        auto_scaling_mode.get_ec2_tags(app) | DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    )
    base_ec2_tags[AWSTagKey("Name")] = AWSTagValue(
        f"{base_ec2_tags[AWSTagKey('Name')]}-buffer"
    )
    return base_ec2_tags


def is_buffer_machine(tags: EC2Tags) -> bool:
    return bool(BUFFER_MACHINE_TAG_KEY in tags)


def dump_pre_pulled_images_as_tags(images: Iterable[DockerGenericTag]) -> EC2Tags:
    # AWS Tag Values are limited to 256 characaters so we chunk the images
    # into smaller chunks
    jsonized_images = json_dumps(images)
    assert AWSTagValue.max_length  # nosec
    if len(jsonized_images) > AWSTagValue.max_length:
        # let's chunk the string
        chunk_size = AWSTagValue.max_length
        chunks = [
            jsonized_images[i : i + chunk_size]
            for i in range(0, len(jsonized_images), chunk_size)
        ]
        return {
            AWSTagKey(f"{PRE_PULLED_IMAGES_EC2_TAG_KEY}_({i})"): AWSTagValue(c)
            for i, c in enumerate(chunks)
        }
    return {
        PRE_PULLED_IMAGES_EC2_TAG_KEY: parse_obj_as(AWSTagValue, json_dumps(images))
    }


def load_pre_pulled_images_from_tags(tags: EC2Tags) -> list[DockerGenericTag]:
    # AWS Tag values are limited to 256 characters so we chunk the images
    if PRE_PULLED_IMAGES_EC2_TAG_KEY in tags:
        # read directly
        return json_loads(tags[PRE_PULLED_IMAGES_EC2_TAG_KEY])

    assembled_json = "".join(
        map(
            itemgetter(1),
            sorted(
                (
                    (int(m.group(1)), value)
                    for key, value in tags.items()
                    if (m := PRE_PULLED_IMAGES_RE.match(key))
                ),
                key=itemgetter(0),
            ),
        )
    )

    return parse_raw_as(list[DockerGenericTag], assembled_json)
