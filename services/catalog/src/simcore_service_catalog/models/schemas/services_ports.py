from typing import Any, Literal, Optional, Union

from models_library.basic_regex import PUBLIC_VARIABLE_NAME_RE
from models_library.services import ServiceInput, ServiceOutput
from models_library.utils.services_io import (
    get_service_io_json_schema,
    guess_media_type,
    update_schema_doc,
)
from pydantic import BaseModel, Field

PortKindStr = Literal["input", "output"]


#
# Model -------------------------------------------------------------------------------
#


class ServicePortGet(BaseModel):
    key: str = Field(
        ...,
        description="port identifier name",
        regex=PUBLIC_VARIABLE_NAME_RE,
        title="Key name",
    )
    kind: PortKindStr
    content_media_type: Optional[str] = None
    content_schema: Optional[dict[str, Any]] = Field(
        None,
        description="jsonschema for the port's value. SEE https://json-schema.org/understanding-json-schema/",
    )

    class Config:
        schema_extra = {
            "example": {
                "key": "input_1",
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
        key: str,
        port: Union[ServiceInput, ServiceOutput],
    ) -> "ServicePortGet":
        kwargs: dict[str, Any] = {"key": key, "kind": kind}

        # Convert old format into schemas
        schema = port.content_schema
        if not schema:
            schema = get_service_io_json_schema(port)

        # Deduce media_type
        if port.property_type.startswith("data:"):
            kwargs["content_media_type"] = guess_media_type(port)
            # Based on https://swagger.io/docs/specification/describing-request-body/file-upload/
            schema = update_schema_doc({"type": "string"}, port)

        kwargs["content_schema"] = schema
        return cls(**kwargs)
