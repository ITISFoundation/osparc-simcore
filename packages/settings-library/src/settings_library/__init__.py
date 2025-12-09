from importlib.metadata import version

from ._constants import CUSTOM_PLACEMENT_LABEL_KEYS

__version__: str = version("simcore-settings-library")

__all__ = ["CUSTOM_PLACEMENT_LABEL_KEYS"]
