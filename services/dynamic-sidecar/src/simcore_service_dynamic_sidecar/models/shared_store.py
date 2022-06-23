from typing import Optional

from pydantic import BaseModel, Field


class SharedStore(BaseModel):
    # TODO: find more concrete name for this dataset! these would be specs for the pod controller
    compose_spec: Optional[str] = Field(
        default=None, description="stores the stringified compose spec"
    )
    container_names: list[str] = Field(
        default_factory=list,
        description="stores the container names from the compose_spec",
    )
