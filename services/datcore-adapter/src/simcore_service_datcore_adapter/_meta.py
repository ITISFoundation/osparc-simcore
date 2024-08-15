""" Application's metadata

"""

from importlib.metadata import distribution, version
from typing import Final

from models_library.basic_types import VersionStr

current_distribution = distribution("simcore_service_datcore_adapter")
__version__ = version("simcore_service_datcore_adapter")

API_VERSION: Final[VersionStr] = __version__
MAJOR, MINOR, PATCH = __version__.split(".")
API_VTAG: Final[str] = f"v{MAJOR}"
PROJECT_NAME: Final[str] = current_distribution.metadata["Name"]


def get_summary() -> str:
    return current_distribution.metadata.get_all("Summary", [""])[-1]


summary: str = get_summary()
