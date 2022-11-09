from copy import deepcopy
from typing import Any, Literal, Optional, Union

from pydantic import schema_of

from ..services import ServiceInput, ServiceOutput
from ..services_constants import PROPERTY_TYPE_TO_PYTHON_TYPE_MAP

PortKindStr = Literal["input", "output"]

_PROPERTY_TYPE_TO_SCHEMAS = {
    property_type: schema_of(python_type, title=property_type.capitalize())
    for property_type, python_type in PROPERTY_TYPE_TO_PYTHON_TYPE_MAP.items()
}


def get_service_io_json_schema(
    port: Union[ServiceInput, ServiceOutput]
) -> Optional[dict[str, Any]]:
    """Get json-schema for a i/o service

    For legacy metadata with property_type = integer, etc ... , it applies a conversion

    NOTE: For the moment, this is a free function. It migh become in the future a member
    of BaseServiceIO once we proceed to a full deprecation of legacy fields like units, etc
    """
    if port.content_schema:
        return deepcopy(port.content_schema)

    # converts legacy
    if schema := _PROPERTY_TYPE_TO_SCHEMAS.get(port.property_type):
        schema = deepcopy(schema)

        # updates schema-doc, i.e description and title
        schema["title"] = port.label
        if port.label != port.description:
            schema["description"] = port.description

        # new x_unit custom field in json-schema
        if port.unit:
            schema["x_unit"] = port.unit

        # updates default
        default = getattr(port, "default_value", None)
        if default is not None:
            schema["default"] = default
        return schema

    return None
