import datetime
from dataclasses import dataclass
from typing import TypeAlias

from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType

InstancePrivateDNSName = str
EC2Tags: TypeAlias = dict[str, str]


@dataclass(frozen=True)
class EC2InstanceData:
    launch_time: datetime.datetime
    id: str  # noqa: A003
    aws_private_dns: InstancePrivateDNSName
    aws_public_ip: str | None
    type: InstanceTypeType  # noqa: A003
    state: InstanceStateNameType
    tags: EC2Tags
