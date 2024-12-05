from copy import deepcopy

from common_library.json_serialization import json_dumps, json_loads
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core.core_schema import CoreSchema


class BaseConfig:
    json_loads = json_loads
    json_dumps = json_dumps


class UriSchema:
    """Metadata class to modify openapi schemas of Url fields

    Usage:
        class TestModel(BaseModel):
            url: Annotated[HttpUrl, UriSchema()]


    will produce a schema for url field property as a string with a format
        {
            "format": "uri",
            "type": "string",
        }

    SEE https://datatracker.ietf.org/doc/html/draft-bhutton-json-schema-validation-00#section-7.3.5
    """

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        # SEE https://docs.pydantic.dev/2.10/concepts/json_schema/#implementing-__get_pydantic_json_schema__
        json_schema = deepcopy(handler(core_schema))

        if (schema := core_schema.get("schema", {})) and schema.get("type") == "url":
            json_schema.update(
                type="string",
                format="uri",
            )
            if max_length := schema.get("max_length"):
                # SEE https://docs.pydantic.dev/2.10/api/networks/#pydantic.networks.UrlConstraints
                # adds limits if schema UrlConstraints includes it (e.g HttUrl includes )
                json_schema.update(maxLength=max_length, minLength=1)

        return json_schema
