from collections.abc import Iterable
from operator import itemgetter
from typing import Final

from aws_library.ec2 import AWS_TAG_VALUE_MAX_LENGTH, AWSTagKey, AWSTagValue, EC2Tags
from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from models_library.docker import DockerGenericTag
from pydantic import TypeAdapter

from ..constants import (
    ACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    BUFFER_MACHINE_TAG_KEY,
    DEACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    PRE_PULLED_IMAGES_EC2_TAG_KEY,
    PRE_PULLED_IMAGES_RE,
)
from ..modules.auto_scaling_mode_base import BaseAutoscaling

_NAME_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("Name")


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
    base_ec2_tags[_NAME_EC2_TAG_KEY] = AWSTagValue(
        f"{base_ec2_tags[_NAME_EC2_TAG_KEY]}-buffer"
    )
    return base_ec2_tags


def is_buffer_machine(tags: EC2Tags) -> bool:
    return bool(BUFFER_MACHINE_TAG_KEY in tags)


def dump_pre_pulled_images_as_tags(images: Iterable[DockerGenericTag]) -> EC2Tags:
    # AWS Tag Values are limited to 256 characaters so we chunk the images
    # into smaller chunks
    jsonized_images = json_dumps(images)
    assert AWS_TAG_VALUE_MAX_LENGTH  # nosec
    if len(jsonized_images) > AWS_TAG_VALUE_MAX_LENGTH:
        # let's chunk the string
        chunk_size = AWS_TAG_VALUE_MAX_LENGTH
        chunks = [
            jsonized_images[i : i + chunk_size]
            for i in range(0, len(jsonized_images), chunk_size)
        ]
        return {
            TypeAdapter(AWSTagKey)
            .validate_python(f"{PRE_PULLED_IMAGES_EC2_TAG_KEY}_{i}"): TypeAdapter(
                AWSTagValue
            )
            .validate_python(c)
            for i, c in enumerate(chunks)
        }
    return {
        PRE_PULLED_IMAGES_EC2_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(
            json_dumps(images)
        )
    }


def load_pre_pulled_images_from_tags(tags: EC2Tags) -> list[DockerGenericTag]:
    # AWS Tag values are limited to 256 characters so we chunk the images
    if PRE_PULLED_IMAGES_EC2_TAG_KEY in tags:
        # read directly
        return TypeAdapter(list[DockerGenericTag]).validate_json(
            tags[PRE_PULLED_IMAGES_EC2_TAG_KEY]
        )

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
    if assembled_json:
        return TypeAdapter(list[DockerGenericTag]).validate_json(assembled_json)
    return []
