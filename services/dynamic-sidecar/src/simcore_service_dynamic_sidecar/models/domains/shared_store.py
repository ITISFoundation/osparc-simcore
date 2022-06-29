from typing import Optional

from pydantic import BaseModel, Field


class SharedStore(BaseModel):
    compose_spec: Optional[str] = Field(
        None, description="stores the stringified compose spec"
    )
    container_names: list[str] = Field(
        [], description="stores the container names from the compose_spec"
    )
