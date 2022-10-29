from typing import Any, Literal, Optional, Union

from models_library.basic_regex import PUBLIC_VARIABLE_NAME_RE
from models_library.services import ServiceInput, ServiceOutput
from pydantic import BaseModel, Field

PortKindStr = Literal["input", "output"]


class ServicePortGet(BaseModel):
    name: str = Field(
        ..., description="port identifier name", regex=PUBLIC_VARIABLE_NAME_RE
    )
    kind: PortKindStr
    content_schema: Optional[dict[str, Any]] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "input_1",
                "kind": "input",
                "content_schema": {
                    "title": "Sleep interval",
                    "type": "integer",
                    "x_unit": "second",
                    "minimum": 0,
                    "maximum": 5,
                },
            }
        }

    @classmethod
    def from_service_io(
        cls,
        kind: PortKindStr,
        name: str,
        io: Union[ServiceInput, ServiceOutput],
    ) -> "ServicePortGet":
        return cls(
            name=name,
            kind=kind,
            content_schema=io.content_schema,
        )
