import logging
import re
from dataclasses import dataclass
from typing import Final

from models_library.generated_models.docker_rest_api import Node

from ..core.errors import Ec2InvalidDnsNameError
from ..modules.ec2 import EC2InstanceData

logger = logging.getLogger(__name__)


_EC2_INTERNAL_DNS_RE: Final[re.Pattern] = re.compile(r"^(?P<ip>ip-[0-9-]+).+$")


def node_host_name_from_ec2_private_dns(
    ec2_instance_data: EC2InstanceData,
) -> str:
    if match := re.match(_EC2_INTERNAL_DNS_RE, ec2_instance_data.aws_private_dns):
        return match.group(1)
    raise Ec2InvalidDnsNameError(aws_private_dns_name=ec2_instance_data.aws_private_dns)


@dataclass(frozen=True)
class AssociatedInstance:
    node: Node
    ec2_instance: EC2InstanceData


async def associate_ec2_instances_with_nodes(
    nodes: list[Node], ec2_instances: list[EC2InstanceData]
) -> tuple[list[AssociatedInstance], list[EC2InstanceData]]:
    """returns the associated and non-associated instances"""
    associated_instances: list[AssociatedInstance] = []
    non_associated_instances: list[EC2InstanceData] = []

    def _find_node_with_name(node: Node) -> bool:
        assert node.Description  # nosec
        return node.Description.Hostname == docker_node_name

    for instance_data in ec2_instances:
        try:
            docker_node_name = node_host_name_from_ec2_private_dns(instance_data)
        except Ec2InvalidDnsNameError:
            logger.exception("Unexcepted EC2 private dns name")
            continue

        if node := next(iter(filter(_find_node_with_name, nodes)), None):
            associated_instances.append(AssociatedInstance(node, instance_data))
        else:
            non_associated_instances.append(instance_data)
    return associated_instances, non_associated_instances
