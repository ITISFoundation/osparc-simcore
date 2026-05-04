from typing import Final

from aws_library.ec2 import AWSTagKey, AWSTagValue, EC2Tags
from aws_library.ec2._models import EC2InstanceBootSpecific
from pydantic import TypeAdapter

from ..constants import (
    ACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    BUFFER_MACHINE_TAG_KEY,
    DEACTIVATED_BUFFER_MACHINE_EC2_TAGS,
)
from ..core.settings import ApplicationSettings
from . import utils_docker

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
