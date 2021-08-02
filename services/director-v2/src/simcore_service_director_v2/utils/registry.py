from typing import Dict

from settings_library.docker_registry import RegistrySettings


def get_dynamic_sidecar_env_vars(registry_settings: RegistrySettings) -> Dict[str, str]:
    return {
        "REGISTRY_AUTH": str(registry_settings.REGISTRY_AUTH),
        "REGISTRY_PATH": str(registry_settings.REGISTRY_PATH),
        "REGISTRY_URL": str(registry_settings.REGISTRY_URL),
        "REGISTRY_USER": str(registry_settings.REGISTRY_USER),
        "REGISTRY_PW": str(registry_settings.REGISTRY_PW.get_secret_value()),
        "REGISTRY_SSL": str(registry_settings.REGISTRY_SSL),
    }
