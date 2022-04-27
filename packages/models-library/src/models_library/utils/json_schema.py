"""
Models and schemas are intimately related.
Here we implement an api on top of jsonschema package adapted for validation of
json-schemas.

SEE service models
"""
# TODO: next step on top could be to construct pydantic models from json-schemas using datamodel-code-generator?

from copy import deepcopy
from typing import Tuple

import jsonschema
from jsonschema import validators

# ERRORS

# alias of jsonschema.exceptions._Error
InvalidJsonSchema = jsonschema.SchemaError
JsonSchemaValidationError = jsonschema.ValidationError


# TODO:  create PydanticValueError and can be raised inside validator
# create also handlers with context managers?
# should construct with jsonschema.*Error?? --> create_from


# VALIDATORS


def _extend_with_default(validator_class):
    # SEE: https://python-jsonschema.readthedocs.io/en/stable/faq/#why-doesn-t-my-schema-s-default-property-set-the-default-on-my-instance
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for prop, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(prop, subschema["default"])

        for error in validate_properties(
            validator,
            properties,
            instance,
            schema,
        ):
            yield error

    return validators.extend(
        validator_class,
        {"properties": set_defaults},
    )


_LATEST_VALIDATOR = validators.validator_for(True)
_EXTENDED_VALIDATOR = _extend_with_default(_LATEST_VALIDATOR)


def jsonschema_validate_data(instance, schema, *, return_with_default: bool = False):
    """
    : raises JsonSchemaValidationError
    """
    assert "$schema" not in schema, "assumes always latest json-schema"  # nosec

    if return_with_default:
        out = deepcopy(instance)
        _EXTENDED_VALIDATOR(schema).validate(out)
    else:
        out = instance
        validators.validate(instance=out, schema=schema, cls=None)

        # TODO: PC validate units? Validate and convert??

    return out


def jsonschema_validate_schema(schema):
    """
    :raises InvalidJsonSchema
    """
    try:
        # TODO: PC validate field x_unit (e.g. fail if x-unit).
        # Check that x-unit is a valid pint-compatible unit?
        # TODO: This should also be added as integration test!
        validators.validate(instance={}, schema=schema)
    except jsonschema.ValidationError:
        pass


__all__: Tuple[str, ...] = (
    "InvalidJsonSchema",
    "JsonSchemaValidationError",
    "jsonschema_validate_schema",
    "jsonschema_validate_data",
)
