from typing import Optional

from pydantic import BaseModel, Field

ContainerNameStr = str


class SharedStore(BaseModel):
    compose_spec: Optional[str] = Field(
        default=None, description="stores the stringified compose spec"
    )
    container_names: list[ContainerNameStr] = Field(
        default_factory=list,
        description="stores the container names from the compose_spec",
    )

    def clear(self):
        self.compose_spec = None
        self.container_names = []
