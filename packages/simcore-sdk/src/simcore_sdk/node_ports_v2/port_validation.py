import logging
import re
from typing import Any

from common_library.errors_classes import OsparcErrorMixin
from models_library.projects_nodes import UnitStr
from models_library.utils.json_schema import (
    JsonSchemaValidationError,
    jsonschema_validate_data,
    jsonschema_validate_schema,
)
from pint import PintError, UnitRegistry

JsonSchemaDict = dict[str, Any]

log = logging.getLogger(__name__)

# ERRORS

#  - Extends PydanticValueError
#  -> Handled in @validator functions and gathered within ValidationError.errors()
#  - Use 'code' to discriminate port_validation errors


class PortValueError(OsparcErrorMixin, ValueError):
    msg_template = "Invalid value in port {port_key!r}: {schema_error_message}"

    # pylint: disable=useless-super-delegation
    def __init__(self, *, port_key: str, schema_error: JsonSchemaValidationError):
        # NOTE: We could extract more info from schema_error (see test_utils_json_schema)
        # but for the moment we are only interested in the message
        super().__init__(
            port_key=port_key,
            schema_error_path=schema_error.absolute_path,
            schema_error_message=schema_error.message,
        )


class PortUnitError(OsparcErrorMixin, ValueError):
    msg_template = "Invalid unit in port {port_key!r}: {pint_error_msg}"

    # pylint: disable=useless-super-delegation
    def __init__(self, *, port_key: str, pint_error: PintError):
        super().__init__(port_key=port_key, pint_error_msg=f"{pint_error}")


# VALIDATORS

# These functions are embedded in a Pydantic validator callback so
# IMO i think it is justified to create a global singleton in memory
# for the units registry. This acts as a cache and its livetime span
# is the same as the service itself.
_THE_UNIT_REGISTRY = UnitRegistry()
UNIT_SUB_PATTERN = re.compile(r"[-\s]")


def _normalize_unit(unit):
    return re.sub(UNIT_SUB_PATTERN, "", unit)


def _validate_port_value(value, content_schema: JsonSchemaDict):
    """validates value against json-schema and replaces defaults"""
    v = jsonschema_validate_data(
        instance=value,
        schema=content_schema,
        return_with_default=True,
    )
    return v


def _validate_port_unit(
    value, unit, content_schema: JsonSchemaDict, *, ureg: UnitRegistry
) -> tuple[Any, UnitStr | None]:
    """
    - Checks valid 'value' against content_schema
    - Converts 'value' with 'unit' to unit expected in content_schema
    """

    if unit:
        unit = _normalize_unit(unit)

        if content_schema["type"] == "object":
            #  unit = {"freq": "Hz", "distances": ["m", "mm"], "other": {"distances": "mm", "frequency": "Hz" }}
            #  unit = "MHz" <-- we have implementd this
            #  unit = "MHz,mm"
            raise NotImplementedError("Units for objects are still not implemented")

    expected_unit = content_schema.get("x_unit")
    if expected_unit:
        expected_unit = _normalize_unit(expected_unit)

        # convert value
        q = ureg.Quantity(value, unit).to(expected_unit)
        value, expected_unit = q.magnitude, f"{q.units}"

    return (value, expected_unit)


def validate_port_content(
    port_key,
    value: Any,
    unit: UnitStr | None,
    content_schema: JsonSchemaDict,
):
    """A port content is all datasets injected to a given port. Currently only
    'value' and 'unit' but it will be extended to more meta info semantics

    The value (i.e. input parameter or output result) is evaluated with task computations and transformed into some outputs
    The rest (currently only units, but in the future other metadata semantics) must also be evaluated and transfomed into
    metadata in the outputs (e.g. output units, etc)

    value is resolved dataset defined in content_schema
    unit is a part of the meta-data and specs can be encoded in content_schema under the x_unit field property

    :raises PortValueError
    :raises PortUnitError
    """
    assert jsonschema_validate_schema(content_schema)  # nosec

    try:
        # port value
        v = _validate_port_value(value, content_schema)
        # extra meta info on port
        u = unit
        if unit:
            v, u = _validate_port_unit(v, unit, content_schema, ureg=_THE_UNIT_REGISTRY)
        return v, u

    except JsonSchemaValidationError as err:
        raise PortValueError(port_key=port_key, schema_error=err) from err

    except PintError as err:
        raise PortUnitError(port_key=port_key, pint_error=err) from err
