from dataclasses import dataclass

from pydantic import ByteSize, PositiveInt


@dataclass(frozen=True)
class EC2InstanceType:
    name: str
    cpus: PositiveInt
    ram: ByteSize
