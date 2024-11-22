import json
import os

from pydantic_settings import BaseSettings

# Expects env var: FUNCTION_SERVICES_AUTHORS='{"OM":{"name": ...}, "EN":{...} }'
try:
    AUTHORS = json.loads(os.environ.get("FUNCTION_SERVICES_AUTHORS", "{}"))
except json.decoder.JSONDecodeError:
    AUTHORS = {}


class FunctionServiceSettings(BaseSettings):
    CATALOG_DEV_FEATURES_ENABLED: bool = False
    DIRECTOR_V2_DEV_FEATURES_ENABLED: bool = False
    WEBSERVER_DEV_FEATURES_ENABLED: bool = False

    def is_dev_feature_enabled(self) -> bool:
        # NOTE that this is imported in these services
        # This solution is not ideal but will suffice
        # until function-services are moved to the database
        return (
            self.CATALOG_DEV_FEATURES_ENABLED
            or self.DIRECTOR_V2_DEV_FEATURES_ENABLED
            or self.WEBSERVER_DEV_FEATURES_ENABLED
        )
