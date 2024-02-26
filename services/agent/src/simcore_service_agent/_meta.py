""" Application's metadata

"""

from importlib.metadata import distribution, version
from typing import Final

from packaging.version import Version

_current_distribution = distribution("simcore-service-agent")
__version__: str = version("simcore-service-agent")


APP_NAME: Final[str] = _current_distribution.metadata["Name"]
VERSION: Final[Version] = Version(__version__)
API_VTAG: str = f"v{VERSION.major}"


def get_summary() -> str:
    return _current_distribution.metadata.get_all("Summary", [""])[-1]


SUMMARY: Final[str] = get_summary()


APP_STARTED_BANNER_MSG = rf"""
     _                                                           _
 ___(_)_ __ ___   ___ ___  _ __ ___        __ _  __ _  ___ _ __ | |_
/ __| | '_ ` _ \ / __/ _ \| '__/ _ \_____ / _` |/ _` |/ _ \ '_ \| __|
\__ \ | | | | | | (_| (_) | | |  __/_____| (_| | (_| |  __/ | | | |_
|___/_|_| |_| |_|\___\___/|_|  \___|      \__,_|\__, |\___|_| |_|\__|
                                                |___/
    {API_VTAG}"""


APP_FINISHED_BANNER_MSG = "{:=^100}".format(
    f"🎉 App {APP_NAME}=={VERSION} shutdown completed 🎉"
)
