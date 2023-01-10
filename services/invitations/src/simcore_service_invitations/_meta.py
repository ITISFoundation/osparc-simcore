""" Application's metadata

"""
from typing import Final

import pkg_resources
from packaging.version import Version
from servicelib.utils_meta import get_summary, get_version_flavours

_current_distribution = pkg_resources.get_distribution("simcore-service-invitations")


PROJECT_NAME: Final[str] = _current_distribution.project_name
VERSION: Final[Version]
API_VTAG: Final[str]

API_VERSION, VERSION, API_VTAG = get_version_flavours(_current_distribution)
__version__: Final[str] = API_VERSION

SUMMARY: Final[str] = get_summary(_current_distribution)


# NOTE: https://texteditor.com/ascii-frames/
APP_STARTED_BANNER_MSG = r"""
         ()()                ____
         (..)               /|o  |
         /\/\  Invitations /o|  o|
        c\db/o............/o_|_o_|  {}
""".format(
    f"v{__version__}"
)


APP_FINISHED_BANNER_MSG = "{:=^100}".format(
    f"🎉 App {PROJECT_NAME}=={__version__} shutdown completed 🎉"
)
