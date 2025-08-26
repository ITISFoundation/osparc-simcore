"""Application's metadata"""

from typing import Final

from models_library.basic_types import VersionStr
from packaging.version import Version
from servicelib.utils_meta import PackageInfo

info: Final = PackageInfo(package_name="simcore-service-dynamic-scheduler")
__version__: Final[VersionStr] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
VERSION: Final[Version] = info.version
API_VERSION: Final[VersionStr] = info.__version__
APP_NAME: Final[str] = info.app_name
API_VTAG: Final[str] = info.api_prefix_path_tag
SUMMARY: Final[str] = info.get_summary()


# NOTE: https://patorjk.com/software/taag/#p=display&f=Standard&t=dynamic-scheduler
APP_STARTED_BANNER_MSG = r"""
      _                             _                    _              _       _
   __| |_   _ _ __   __ _ _ __ ___ (_) ___      ___  ___| |__   ___  __| |_   _| | ___ _ __
  / _` | | | | '_ \ / _` | '_ ` _ \| |/ __|____/ __|/ __| '_ \ / _ \/ _` | | | | |/ _ \ '__|
 | (_| | |_| | | | | (_| | | | | | | | (_|_____\__ \ (__| | | |  __/ (_| | |_| | |  __/ |
  \__,_|\__, |_| |_|\__,_|_| |_| |_|_|\___|    |___/\___|_| |_|\___|\__,_|\__,_|_|\___|_|
        |___/                                                                                 {}
""".format(
    f"v{__version__}"
)


APP_FINISHED_BANNER_MSG = info.get_finished_banner()
