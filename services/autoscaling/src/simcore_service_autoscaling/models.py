from pydantic import BaseModel, ByteSize, NonNegativeFloat, PositiveInt


class Resources(BaseModel):
    cpus: NonNegativeFloat
    ram: ByteSize


class EC2Instance(BaseModel):
    name: str
    cpus: PositiveInt
    ram: ByteSize
