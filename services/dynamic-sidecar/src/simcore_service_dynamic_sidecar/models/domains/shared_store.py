from typing import List, Optional

from pydantic import BaseModel, Field


class SharedStore(BaseModel):
    compose_spec: Optional[str] = Field(
        None, description="stores the stringified compose spec"
    )
    container_names: List[str] = Field(
        [], description="stores the container names from the compose_spec"
    )
