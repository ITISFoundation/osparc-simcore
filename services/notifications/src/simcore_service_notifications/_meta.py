"""Application's metadata"""

from importlib.metadata import distribution, version
from typing import Final

from packaging.version import Version

_current_distribution = distribution("simcore-service-notifications")
__version__: str = version("simcore-service-notifications")


APP_NAME: Final[str] = _current_distribution.metadata["Name"]
VERSION: Final[Version] = Version(__version__)
API_VTAG: str = f"v{VERSION.major}"


def get_summary() -> str:
    return _current_distribution.metadata.get_all("Summary", [""])[-1]


SUMMARY: Final[str] = get_summary()


APP_STARTED_BANNER_MSG = rf"""
 _______            _    ___ _                   _
(_______)       _  (_)  / __(_)              _  (_)
 _     _  ___ _| |_ _ _| |__ _  ____ _____ _| |_ _  ___  ____   ___
| |   | |/ _ (_   _| (_   __| |/ ___(____ (_   _| |/ _ \|  _ \ /___)
| |   | | |_| || |_| | | |  | ( (___/ ___ | | |_| | |_| | | | |___ |
|_|   |_|\___/  \__|_| |_|  |_|\____\_____|  \__|_|\___/|_| |_(___/
    {API_VTAG}"""


APP_FINISHED_BANNER_MSG = "{:=^100}".format(
    f"🎉 App {APP_NAME}=={VERSION} shutdown completed 🎉"
)
