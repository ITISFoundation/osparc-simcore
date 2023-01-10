""" Application's metadata

"""
from contextlib import suppress
from typing import Final

import pkg_resources
from packaging.version import Version

_current_distribution = pkg_resources.get_distribution("simcore-service-invitations")
__version__: str = _current_distribution.version


APP_NAME: Final[str] = _current_distribution.project_name
API_VERSION: str = __version__
VERSION: Final[str] = Version(__version__)
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


APP_STARTED_BANNER_MSG = r"""
. _   ._|_ _ _|_. _  _  _
|| |\/| | (_| | |(_)| |_\    {}
""".format(
    f"v{__version__}"
)


APP_FINISHED_BANNER_MSG = "{:=^100}".format(
    f"🎉 App {APP_NAME}=={__version__} shutdown completed 🎉"
)
