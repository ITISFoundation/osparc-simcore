from collections.abc import Iterable
from operator import itemgetter
from typing import Final

from aws_library.ec2 import AWS_TAG_VALUE_MAX_LENGTH, AWSTagKey, AWSTagValue, EC2Tags
from aws_library.ec2._models import EC2InstanceBootSpecific
from common_library.json_serialization import json_dumps
from models_library.docker import DockerGenericTag
from pydantic import TypeAdapter

from ..constants import (
    ACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    BUFFER_MACHINE_TAG_KEY,
    DEACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    PRE_PULLED_IMAGES_EC2_TAG_KEY,
    PRE_PULLED_IMAGES_RE,
)
from ..core.settings import ApplicationSettings
from . import utils_docker

_NAME_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("Name")


def get_activated_warm_buffer_ec2_tags(base_ec2_tags: EC2Tags) -> EC2Tags:
    return base_ec2_tags | ACTIVATED_BUFFER_MACHINE_EC2_TAGS


def get_deactivated_buffer_ec2_tags(base_ec2_tags: EC2Tags) -> EC2Tags:
    new_base_ec2_tags = base_ec2_tags | DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    new_base_ec2_tags[_NAME_EC2_TAG_KEY] = TypeAdapter(AWSTagValue).validate_python(
        f"{new_base_ec2_tags[_NAME_EC2_TAG_KEY]}-buffer"
    )
    return new_base_ec2_tags


def is_warm_buffer_machine(tags: EC2Tags) -> bool:
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


def ec2_buffer_startup_script(
    ec2_boot_specific: EC2InstanceBootSpecific, app_settings: ApplicationSettings
) -> str:
    startup_commands = ec2_boot_specific.custom_boot_scripts.copy()
    if ec2_boot_specific.pre_pull_images:
        assert app_settings.AUTOSCALING_REGISTRY  # nosec
        startup_commands.extend(
            (
                utils_docker.get_docker_login_on_start_bash_command(
                    app_settings.AUTOSCALING_REGISTRY
                ),
                utils_docker.write_compose_file_command(
                    ec2_boot_specific.pre_pull_images
                ),
            )
        )
    return " && ".join(startup_commands)
