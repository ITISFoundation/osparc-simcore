import json
import logging
from pathlib import Path

# NOTE: currently uses draft04 version
from jsonschema import (SchemaError, 
                        ValidationError, 
                        validate)

_logger = logging.getLogger(__name__)

def validate_instance_object(json_instance: dict, json_schema: dict):
    try:
        validate(json_instance, json_schema)
    except ValidationError:
        _logger.exception("Node validation error:")
        raise
    except SchemaError:
        _logger.exception("Schema validation error:")
        raise

def validate_instance_path(json_instance: Path, json_schema: Path):
    with json_instance.open() as file_pointer:
        instance = json.load(file_pointer)
    
    with json_schema.open() as file_pointer:
        schema = json.load(file_pointer)
    
    validate_instance_object(instance, schema)