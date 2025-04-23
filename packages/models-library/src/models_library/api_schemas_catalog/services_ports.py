from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

from ..basic_regex import PUBLIC_VARIABLE_NAME_RE
from ..services import ServiceInput, ServiceOutput
from ..utils.services_io import (
    get_service_io_json_schema,
    guess_media_type,
    update_schema_doc,
)


class ServicePortGet(BaseModel):
    key: Annotated[
        str,
        Field(
            description="Port identifier name",
            pattern=PUBLIC_VARIABLE_NAME_RE,
            title="Key name",
        ),
    ]
    kind: Literal["input", "output"]
    content_media_type: str | None = None
    content_schema: Annotated[
        dict[str, Any] | None,
        Field(
            description="jsonschema for the port's value. SEE https://json-schema.org/understanding-json-schema/",
        ),
    ] = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        example_input: dict[str, Any] = {
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
        schema.update(
            {
                "example": example_input,
                "examples": [
                    example_input,
                    {
                        "key": "output_1",
                        "kind": "output",
                        "content_media_type": "text/plain",
                        "content_schema": {
                            "type": "string",
                            "title": "File containing one random integer",
                            "description": "Integer is generated in range [1-9]",
                        },
                    },
                ],
            }
        )

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )

    @classmethod
    def from_domain_model(
        cls,
        kind: Literal["input", "output"],
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
