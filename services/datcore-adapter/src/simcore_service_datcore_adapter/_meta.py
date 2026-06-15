"""Application's metadata"""

from importlib.metadata import distribution, version
from typing import Final

from models_library.basic_types import VersionStr
from pydantic import TypeAdapter

current_distribution = distribution("simcore_service_datcore_adapter")
__version__ = version("simcore_service_datcore_adapter")

API_VERSION: Final[VersionStr] = TypeAdapter(VersionStr).validate_python(__version__)
MAJOR, MINOR, PATCH = __version__.split(".")
API_VTAG: Final[str] = f"v{MAJOR}"
APP_NAME: Final[str] = current_distribution.metadata["Name"]
PROJECT_NAME: Final[str] = current_distribution.metadata["Name"]


def get_summary() -> str:
    return current_distribution.metadata.get_all("Summary", [""])[-1]


SUMMARY: Final[str] = get_summary()
summary: str = SUMMARY


APP_STARTED_BANNER_MSG: Final[str] = "{:=^100}".format(f"Datcore-Adapter v{__version__}")


APP_STARTING_BANNER_MSG: Final[str] = "{:=^100}".format(f"Starting {APP_NAME} v{__version__}")
APP_FINISHED_BANNER_MSG: Final[str] = "{:=^100}".format(f"{PROJECT_NAME} v{__version__} SHUT DOWN")
