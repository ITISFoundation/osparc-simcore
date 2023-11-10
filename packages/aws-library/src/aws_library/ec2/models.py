import datetime
from dataclasses import dataclass
from typing import TypeAlias

from pydantic import BaseModel, ByteSize, NonNegativeFloat, PositiveInt
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType


class Resources(BaseModel):
    cpus: NonNegativeFloat
    ram: ByteSize

    @classmethod
    def create_as_empty(cls) -> "Resources":
        return cls(cpus=0, ram=ByteSize(0))

    def __ge__(self, other: "Resources") -> bool:
        return self.cpus >= other.cpus and self.ram >= other.ram

    def __gt__(self, other: "Resources") -> bool:
        return self.cpus > other.cpus or self.ram > other.ram

    def __add__(self, other: "Resources") -> "Resources":
        return Resources.construct(
            **{
                key: a + b
                for (key, a), b in zip(
                    self.dict().items(), other.dict().values(), strict=True
                )
            }
        )

    def __sub__(self, other: "Resources") -> "Resources":
        return Resources.construct(
            **{
                key: a - b
                for (key, a), b in zip(
                    self.dict().items(), other.dict().values(), strict=True
                )
            }
        )


@dataclass(frozen=True)
class EC2InstanceType:
    name: InstanceTypeType
    cpus: PositiveInt
    ram: ByteSize


InstancePrivateDNSName: TypeAlias = str
EC2Tags: TypeAlias = dict[str, str]


@dataclass(frozen=True)
class EC2InstanceData:
    launch_time: datetime.datetime
    id: str  # noqa: A003
    aws_private_dns: InstancePrivateDNSName
    type: InstanceTypeType  # noqa: A003
    state: InstanceStateNameType
    resources: Resources
