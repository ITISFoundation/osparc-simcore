import logging
from typing import Any, Dict, Optional, Tuple

import jsonschema
from models_library.projects_nodes import UnitStr
from pint import UnitRegistry
from pydantic.errors import PydanticValueError

from .utils_schemas import jsonschema_validate_data, jsonschema_validate_schema

JsonSchemaDict = Dict[str, Any]

log = logging.getLogger(__name__)

# ERRORS
#   Extends PydanticValueError to discriminate schema validation errors


class PortSchemaValidationError(PydanticValueError):
    code = "port_schema_validation_error"
    msg_template = "{port_key} value does not fulfill port's content schema: {schema_error.message}"

    # pylint: disable=useless-super-delegation
    def __init__(self, *, port_key: str, schema_error: jsonschema.ValidationError):
        super().__init__(port_key=port_key, schema_error=schema_error)


# VALIDATORS

# These functions are embedded in a Pydantic validator callback so
# IMO i think it is justified to create a global singleton in memory
# for the units registry. This acts as a cache that will be restarted
# with the service.
_THE_UNIT_REGISTRY = UnitRegistry()


def _validate_port_value(value, content_schema: JsonSchemaDict):
    v = jsonschema_validate_data(
        instance=value,
        schema=content_schema,
        return_with_default=True,
    )
    return v


def _validate_port_quantity(
    value, unit, content_schema: JsonSchemaDict, ureg: UnitRegistry = _THE_UNIT_REGISTRY
) -> Tuple:
    # TODO:
    #  unit = {"freq": "Hz", "distances": ["m", "mm"], "other": {"distances": "mm", "frequency": "Hz" }}
    #  unit = "MHz" <-- we start here
    #  unit = "MHz,mm"
    # is unit valid? compatible with x_unit?

    if unit:
        if content_schema["type"] == "object":
            raise NotImplementedError("Units for objects are still not implemented")

    expected_unit = content_schema.get("x_unit")
    if expected_unit:
        # convert value
        new_quantity = ureg.Quantity(value, unit).to(expected_unit)
        value = new_quantity.value

    return (value, expected_unit)


def validate_port_content(
    port_key,
    value: Any,
    unit: Optional[UnitStr],
    content_schema: JsonSchemaDict,
):
    """A port content is all datasets injected to a given port. Currently only
    'value' and 'unit' but it will be extended to more meta info semantics

    The value (i.e. input parameter or output result) is evaluated with task computations and transformed into some outputs
    The rest (currently only units, but in the future other metadata semantics) must also be evaluated and transfomed into
    metadata in the outputs (e.g. output units, etc)

    value is resolved dataset defined in content_schema
    unit is a part of the meta-data and specs can be encoded in content_schema under the x_unit field property
    """
    assert jsonschema_validate_schema(content_schema)  # nosec

    try:
        # port value
        v = _validate_port_value(value, content_schema)
        # extra meta info on port
        u = unit
        if unit:
            v, u = _validate_port_quantity(v, unit, content_schema)
        return v, u
    except jsonschema.ValidationError as err:
        raise PortSchemaValidationError(port_key=port_key, schema_error=err) from err
