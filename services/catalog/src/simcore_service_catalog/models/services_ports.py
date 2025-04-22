from typing import Annotated, Literal

from models_library.services_io import ServiceInput, ServiceOutput
from pydantic import BaseModel, Field


class ServicePort(BaseModel):
    kind: Annotated[
        Literal["input", "output"],
        Field(description="Whether this is an input or output port"),
    ]
    key: Annotated[
        str, Field(description="The unique identifier for this port within the service")
    ]
    port: ServiceInput | ServiceOutput
