import datetime
from dataclasses import dataclass
from typing import TypeAlias

from pydantic import ByteSize, PositiveInt
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType


@dataclass(frozen=True)
class EC2InstanceType:
    name: str
    cpus: PositiveInt
    ram: ByteSize


InstancePrivateDNSName = str
EC2Tags: TypeAlias = dict[str, str]


@dataclass(frozen=True)
class EC2InstanceData:
    launch_time: datetime.datetime
    id: str  # noqa: A003
    aws_private_dns: InstancePrivateDNSName
    type: InstanceTypeType  # noqa: A003
    state: InstanceStateNameType
    tags: EC2Tags


@dataclass(frozen=True)
class Cluster:
    ...
