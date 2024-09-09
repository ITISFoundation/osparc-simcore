from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..basic_regex import PUBLIC_VARIABLE_NAME_RE
from ..services import ServiceInput, ServiceOutput
from ..utils.services_io import (
    get_service_io_json_schema,
    guess_media_type,
    update_schema_doc,
)

PortKindStr = Literal["input", "output"]


class ServicePortGet(BaseModel):
    key: str = Field(
        ...,
        description="port identifier name",
        pattern=PUBLIC_VARIABLE_NAME_RE,
        title="Key name",
    )
    kind: PortKindStr
    content_media_type: str | None = None
    content_schema: dict[str, Any] | None = Field(
        None,
        description="jsonschema for the port's value. SEE https://json-schema.org/understanding-json-schema/",
    )
    model_config = ConfigDict(
        json_schema_extra={
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
    )

    @classmethod
    def from_service_io(
        cls,
        kind: PortKindStr,
        key: str,
        port: ServiceInput | ServiceOutput,
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
