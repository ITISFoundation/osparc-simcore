from dataclasses import dataclass

from pydantic.v1 import ByteSize, NonNegativeFloat


@dataclass(frozen=True)
class EC2InstanceTypeGet:
    name: str
    cpus: NonNegativeFloat
    ram: ByteSize
