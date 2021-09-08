import logging
from typing import Dict

from jsonschema import SchemaError, ValidationError, validate

log = logging.getLogger(__name__)


def validate_instance(instance: Dict, schema: Dict, *, log_errors=True):
    try:
        validate(instance, schema)
    except ValidationError:
        if log_errors:
            log.exception("Node validation error:")
        raise
    except SchemaError:
        if log_errors:
            log.exception("Schema validation error:")
        raise
