"""Application's metadata"""

from typing import Final

from models_library.basic_types import VersionStr
from packaging.version import Version
from servicelib.utils_meta import PackageInfo
from settings_library.basic_types import VersionTag

info: Final = PackageInfo(package_name="simcore-service-invitations")
__version__: Final[VersionStr] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
VERSION: Final[Version] = info.version
API_VERSION: Final[VersionStr] = info.__version__
APP_NAME: Final[str] = info.app_name
API_VTAG: Final[VersionTag] = VersionTag(info.api_prefix_path_tag)
SUMMARY: Final[str] = info.get_summary()


# NOTE: https://texteditor.com/ascii-frames/
APP_STARTED_BANNER_MSG = r"""
         ()()                ____
         (..)               /|o  |
         /\/\  Invitations /o|  o|
        c\db/o............/o_|_o_|  {}
""".format(
    f"v{__version__}"
)


APP_FINISHED_BANNER_MSG = info.get_finished_banner()
