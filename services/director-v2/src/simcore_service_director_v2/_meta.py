"""Application's metadata."""

from typing import Final

from models_library.basic_types import VersionStr
from packaging.version import Version
from servicelib.utils_meta import PackageInfo

info: Final = PackageInfo(package_name="simcore-service-director-v2")
__version__: Final[VersionStr] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
VERSION: Final[Version] = info.version
API_VERSION: Final[VersionStr] = info.__version__
API_VTAG: Final[str] = info.api_prefix_path_tag
APP_NAME: Final[str] = info.app_name
SUMMARY: Final[str] = info.get_summary()

APP_STARTING_BANNER_MSG = info.get_starting_banner()

#
# SEE https://patorjk.com/software/taag/#p=display&f=Small&t=Director
#
APP_STARTED_BANNER_MSG = r"""
______ _               _
|  _  (_)             | |
| | | |_ _ __ ___  ___| |_ ___  _ __
| | | | | '__/ _ \/ __| __/ _ \| '__|
| |/ /| | | |  __/ (__| || (_) | |
|___/ |_|_|  \___|\___|\__\___/|_|   {}

""".format(f"v{__version__}")

APP_FINISHED_BANNER_MSG = info.get_finished_banner()
