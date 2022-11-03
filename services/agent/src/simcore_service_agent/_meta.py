""" Application's metadata

"""
from contextlib import suppress
from typing import Final

import pkg_resources
from packaging.version import Version

_current_distribution = pkg_resources.get_distribution("simcore-service-agent")
__version__: str = _current_distribution.version


APP_NAME: Final[str] = _current_distribution.project_name
VERSION: Final[Version] = Version(__version__)
API_VTAG: str = f"v{VERSION.major}"


def get_summary() -> str:
    with suppress(Exception):
        try:
            metadata = _current_distribution.get_metadata_lines("METADATA")
        except FileNotFoundError:
            metadata = _current_distribution.get_metadata_lines("PKG-INFO")

        return next(x.split(":") for x in metadata if x.startswith("Summary:"))[-1]
    return ""


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
