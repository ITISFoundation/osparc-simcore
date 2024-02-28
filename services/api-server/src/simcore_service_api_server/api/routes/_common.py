from typing import Final

from ...core.settings import BasicSettings

API_SERVER_DEV_FEATURES_ENABLED: Final[
    bool
] = BasicSettings.create_from_envs().API_SERVER_DEV_FEATURES_ENABLED
