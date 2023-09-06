""" Application's metadata

"""
from contextlib import suppress
from typing import Final

import pkg_resources
from packaging.version import Version

_current_distribution = pkg_resources.get_distribution("simcore-service-autoscaling")

__version__: str = _current_distribution.version


APP_NAME: Final[str] = _current_distribution.project_name
API_VERSION: Final[str] = __version__
VERSION: Final[Version] = Version(__version__)
API_VTAG: Final[str] = f"v{VERSION.major}"


def get_summary() -> str:
    with suppress(Exception):
        try:
            metadata = _current_distribution.get_metadata_lines("METADATA")
        except FileNotFoundError:
            metadata = _current_distribution.get_metadata_lines("PKG-INFO")

        return next(x.split(":") for x in metadata if x.startswith("Summary:"))[-1]
    return ""  # pragma: no cover


SUMMARY: Final[str] = get_summary()


# https://patorjk.com/software/taag/#p=testall&f=Avatar&t=Autoscaling
APP_STARTED_BANNER_MSG = r"""
                _                      _ _
     /\        | |                    | (_)
    /  \  _   _| |_ ___  ___  ___ __ _| |_ _ __   __ _
   / /\ \| | | | __/ _ \/ __|/ __/ _` | | | '_ \ / _` |
  / ____ \ |_| | || (_) \__ \ (_| (_| | | | | | | (_| |
 /_/    \_\__,_|\__\___/|___/\___\__,_|_|_|_| |_|\__, |
                                                  __/ |
                                                 |___/       {}
""".format(
    f"v{__version__}"
)


APP_FINISHED_BANNER_MSG = "{:=^100}".format(
    f"🎉 App {APP_NAME}=={__version__} shutdown completed 🎉"
)
