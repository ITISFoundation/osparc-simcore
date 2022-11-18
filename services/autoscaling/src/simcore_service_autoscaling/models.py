from pydantic import BaseModel, ByteSize


class ClusterResources(BaseModel):
    total_cpus: int
    total_ram: ByteSize
