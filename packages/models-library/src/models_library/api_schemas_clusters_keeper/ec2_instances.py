from dataclasses import dataclass

from pydantic import ByteSize, PositiveInt


@dataclass(frozen=True)
class EC2InstanceTypeGet:
    name: str
    cpus: PositiveInt
    ram: ByteSize
