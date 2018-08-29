import json
import logging
from jsonschema import SchemaError, ValidationError, validate

from simcore_service_director import exceptions, config

_LOGGER = logging.getLogger(__name__)

node_schema_file = config.JSON_SCHEMA_BASE_FOLDER / config.NODE_JSON_SCHEMA_FILE
with node_schema_file.open() as fp:
    schema = json.load(fp)

def validate_nodes(services):
    validated_services = []
    for service in services:
        try:
            validate(service, schema)
            validated_services.append(service)
            _LOGGER.debug("service [%s] validated", service["key"])
        except ValidationError:
            _LOGGER.exception("Node validation error:")
            # let's skip this service            
            continue
        except SchemaError:
            _LOGGER.exception("Schema error:")
            raise exceptions.DirectorException("Incorrect json schema used from %s" % (node_schema_file))        
    return validated_services