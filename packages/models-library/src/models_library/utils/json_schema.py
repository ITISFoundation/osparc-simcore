"""
Models and schemas are intimately related.
Here we implement an api on top of jsonschema package adapted for validation of
json-schemas.

See how is used to validate input/output content-schemas of service models
"""
# SEE possible enhancements in https://github.com/ITISFoundation/osparc-simcore/issues/3008


from contextlib import suppress
from copy import deepcopy
from typing import Any, Dict, Tuple

import jsonschema
from jsonschema import validators

# ERRORS

# alias for jsonschema.exceptions._Error subclasses
InvalidJsonSchema = jsonschema.SchemaError
JsonSchemaValidationError = jsonschema.ValidationError


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


def jsonschema_validate_data(
    instance: Any, schema: Dict[str, Any], *, return_with_default: bool = False
):
    """Checks whether data satisfies schema contract

    : raises JsonSchemaValidationError
    """
    assert "$schema" not in schema, "assumes always latest json-schema"  # nosec

    if return_with_default:
        out = deepcopy(instance)
        _EXTENDED_VALIDATOR(schema).validate(out)
    else:
        out = instance
        validators.validate(instance=out, schema=schema, cls=None)
        # SEE possible extension in https://github.com/ITISFoundation/osparc-simcore/issues/3009
    return out


def jsonschema_validate_schema(schema: Dict[str, Any]):
    """Checks whether schema is a valid json-schema

    :raises InvalidJsonSchema
    """
    with suppress(jsonschema.ValidationError):
        dummy_data = {}
        validators.validate(instance=dummy_data, schema=schema)
    return schema


__all__: Tuple[str, ...] = (
    "InvalidJsonSchema",
    "JsonSchemaValidationError",
    "jsonschema_validate_schema",
    "jsonschema_validate_data",
)
