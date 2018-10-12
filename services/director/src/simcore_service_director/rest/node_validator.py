import json
import logging

from jsonschema import (
    SchemaError, 
    ValidationError, 
    validate)
from simcore_service_director import (
    exceptions, 
    resources)

log = logging.getLogger(__name__)


with resources.stream(resources.RESOURCE_NODE_SCHEMA) as fp:
    schema = json.load(fp)

def is_service_valid(service):
    try:
        validate(service, schema)
        log.debug("service [%s] validated", service["key"])
        return True
    except ValidationError:
        log.exception("Node validation error:")
        return False
    except SchemaError:
        log.exception("Schema error:")        
        raise exceptions.DirectorException("Incorrect json schema used from %s" % (resources.get_path(resources.RESOURCE_NODE_SCHEMA)))

def validate_nodes(services):
    validated_services = []
    for service in services:
        if is_service_valid(service):
            validated_services.append(service)
    return validated_services
