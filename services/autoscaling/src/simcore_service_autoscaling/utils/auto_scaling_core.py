import logging
import re
from typing import Final

from models_library.generated_models.docker_rest_api import Node

from ..core.errors import Ec2InvalidDnsNameError
from ..core.settings import ApplicationSettings
from ..models import AssociatedInstance, EC2InstanceData
from . import utils_docker

_EC2_INTERNAL_DNS_RE: Final[re.Pattern] = re.compile(r"^(?P<host_name>ip-[^.]+).*$")
_logger = logging.getLogger(__name__)


def node_host_name_from_ec2_private_dns(
    ec2_instance_data: EC2InstanceData,
) -> str:
    """returns the node host name 'ip-10-2-3-22' from the ec2 private dns
    Raises:
        Ec2InvalidDnsNameError: if the dns name does not follow the expected pattern
    """
    if match := re.match(_EC2_INTERNAL_DNS_RE, ec2_instance_data.aws_private_dns):
        return match.group("host_name")
    raise Ec2InvalidDnsNameError(aws_private_dns_name=ec2_instance_data.aws_private_dns)


def node_ip_from_ec2_private_dns(
    ec2_instance_data: EC2InstanceData,
) -> str:
    """returns the node ipv4 from the ec2 private dns string
    Raises:
        Ec2InvalidDnsNameError: if the dns name does not follow the expected pattern
    """
    return (
        node_host_name_from_ec2_private_dns(ec2_instance_data)
        .removeprefix("ip-")
        .replace("-", ".")
    )


async def associate_ec2_instances_with_nodes(
    nodes: list[Node], ec2_instances: list[EC2InstanceData]
) -> tuple[list[AssociatedInstance], list[EC2InstanceData]]:
    """returns the associated and non-associated instances"""
    associated_instances: list[AssociatedInstance] = []
    non_associated_instances: list[EC2InstanceData] = []

    def _find_node_with_name(node: Node) -> bool:
        assert node.Description  # nosec
        return bool(node.Description.Hostname == docker_node_name)

    for instance_data in ec2_instances:
        try:
            docker_node_name = node_host_name_from_ec2_private_dns(instance_data)
        except Ec2InvalidDnsNameError:
            _logger.exception("Unexcepted EC2 private dns name")
            non_associated_instances.append(instance_data)
            continue

        if node := next(iter(filter(_find_node_with_name, nodes)), None):
            associated_instances.append(AssociatedInstance(node, instance_data))
        else:
            non_associated_instances.append(instance_data)
    return associated_instances, non_associated_instances


async def ec2_startup_script(app_settings: ApplicationSettings) -> str:
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    startup_commands = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_CUSTOM_BOOT_SCRIPTS.copy()
    )
    startup_commands.append(await utils_docker.get_docker_swarm_join_bash_command())
    if app_settings.AUTOSCALING_REGISTRY:
        startup_commands.append(
            utils_docker.get_docker_login_on_start_bash_command(
                app_settings.AUTOSCALING_REGISTRY
            )
        )
        if pull_image_cmd := utils_docker.get_docker_pull_images_on_start_bash_command(
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_PRE_PULL_IMAGES
        ):
            startup_commands.append(pull_image_cmd)
            startup_commands.append(
                utils_docker.get_docker_pull_images_crontab(
                    app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_PRE_PULL_IMAGES_CRON_INTERVAL
                ),
            )

    return " && ".join(startup_commands)
