from pathlib import Path


class BaseServicesPreferencesError(Exception):
    ...


class DestinationIsNotADirectoryError(BaseServicesPreferencesError):
    def __init__(self, destination_to: Path) -> None:
        super().__init__(f"Provided {destination_to=} must be a directory")


class PreferencesAreTooBigError(BaseServicesPreferencesError):
    def __init__(self, size: int, limit: int) -> None:
        super().__init__(
            f"Preferences amount to a size of {size=} bytes. Allowed {limit=} bytes."
        )
