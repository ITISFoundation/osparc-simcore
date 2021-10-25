import json
from typing import Dict

from settings_library.docker_registry import RegistrySettings
from settings_library.rabbit import RabbitSettings


def get_dynamic_sidecar_env_vars(
    registry_settings: RegistrySettings, rabbit_settings: RabbitSettings
) -> Dict[str, str]:
    return {
        "REGISTRY_AUTH": str(registry_settings.REGISTRY_AUTH),
        "REGISTRY_PATH": str(registry_settings.REGISTRY_PATH),
        "REGISTRY_URL": str(registry_settings.REGISTRY_URL),
        "REGISTRY_USER": str(registry_settings.REGISTRY_USER),
        "REGISTRY_PW": str(registry_settings.REGISTRY_PW.get_secret_value()),
        "REGISTRY_SSL": str(registry_settings.REGISTRY_SSL),
        "RABBIT_HOST": str(rabbit_settings.RABBIT_HOST),
        "RABBIT_PORT": str(rabbit_settings.RABBIT_PORT),
        "RABBIT_USER": str(rabbit_settings.RABBIT_USER),
        "RABBIT_PASSWORD": str(rabbit_settings.RABBIT_PASSWORD.get_secret_value()),
        "RABBIT_CHANNELS": json.dumps(rabbit_settings.RABBIT_CHANNELS),
    }
