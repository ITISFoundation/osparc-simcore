from typing import Optional

from settings_library.r_clone import RCloneSettings


def get_r_clone_settings(settings: RCloneSettings) -> Optional[RCloneSettings]:
    return settings if settings.R_CLONE_ENABLED else None
