import logging
from typing import Dict

from jsonschema import SchemaError, ValidationError, validate

log = logging.getLogger(__name__)

def validate_instance(instance: Dict, schema: Dict):
    try:
        validate(instance, schema)
    except ValidationError:
        log.exception("Node validation error:")
        raise
    except SchemaError:
        log.exception("Schema validation error:")
        raise
