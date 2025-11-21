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


## https://patorjk.com/software/taag/#p=display&f=Standard&t=Notifications
APP_STARTED_BANNER_MSG = rf"""
  _   _       _   _  __ _           _   _
 | \ | | ___ | |_(_)/ _(_) ___ __ _| |_(_) ___  _ __  ___
 |  \| |/ _ \| __| | |_| |/ __/ _` | __| |/ _ \| '_ \/ __|
 | |\  | (_) | |_| |  _| | (_| (_| | |_| | (_) | | | \__ \
 |_| \_|\___/ \__|_|_| |_|\___\__,_|\__|_|\___/|_| |_|___/
    {API_VTAG}"""


APP_WORKER_STARTED_BANNER_MSG = rf"""
  _   _       _   _  __ _           _   _                    __        __         _
 | \ | | ___ | |_(_)/ _(_) ___ __ _| |_(_) ___  _ __  ___    \ \      / /__  _ __| | _____ _ __
 |  \| |/ _ \| __| | |_| |/ __/ _` | __| |/ _ \| '_ \/ __|____\ \ /\ / / _ \| '__| |/ / _ \ '__|
 | |\  | (_) | |_| |  _| | (_| (_| | |_| | (_) | | | \__ \_____\ V  V / (_) | |  |   <  __/ |
 |_| \_|\___/ \__|_|_| |_|\___\__,_|\__|_|\___/|_| |_|___/      \_/\_/ \___/|_|  |_|\_\___|_|
    {API_VTAG}"""


APP_SHUTDOWN_BANNER_MSG = "{:=^100}".format(
    f"🎉 App {APP_NAME}=={VERSION} shutdown completed 🎉"
)
