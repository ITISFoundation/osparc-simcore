import logging
from copy import deepcopy

import jsonschema
from jsonschema import validators

log = logging.getLogger(__name__)


def extend_with_default(validator_class):
    # SEE: https://python-jsonschema.readthedocs.io/en/stable/faq/#why-doesn-t-my-schema-s-default-property-set-the-default-on-my-instance
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(property, subschema["default"])

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
_EXTENDED_VALIDATOR = extend_with_default(_LATEST_VALIDATOR)


def jsonschema_validate_data(instance, schema, *, return_with_default: bool = False):
    assert "$schema" not in schema, "assumes always latest json-schema"  # nosec

    if return_with_default:
        out = deepcopy(instance)
        _EXTENDED_VALIDATOR(schema).validate(out)
    else:
        out = instance
        validators.validate(out, schema, cls=None)

    return out


def jsonschema_validate_schema(schema):
    try:
        validators.validate(instance={}, schema=schema)
    except jsonschema.ValidationError:
        pass
