import json
import logging

from jsonschema import (
    SchemaError,
    ValidationError,
    validate
)

from simcore_service_director import (
    exceptions, 
    config)

_LOGGER = logging.getLogger(__name__)

_NODE_SCHENA_FILE = config.JSON_SCHEMA_BASE_FOLDER / config.NODE_JSON_SCHEMA_FILE
with _NODE_SCHENA_FILE.open() as fp:
    schema = json.load(fp)

def is_service_valid(service):
    try:
        validate(service, schema)
        _LOGGER.debug("service [%s] validated", service["key"])
        return True
    except ValidationError:
        _LOGGER.exception("Node validation error:")
        return False
    except SchemaError:
        _LOGGER.exception("Schema error:")
        raise exceptions.DirectorException("Incorrect json schema used from %s" % (_NODE_SCHENA_FILE))

def validate_nodes(services):
    validated_services = []
    for service in services:
        if is_service_valid(service):
            validated_services.append(service)
    return validated_services
