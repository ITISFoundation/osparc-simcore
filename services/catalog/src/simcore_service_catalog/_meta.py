from typing import Final

from models_library.basic_types import VersionStr
from packaging.version import Version
from servicelib.utils_meta import PackageInfo

info: Final = PackageInfo(package_name="simcore-service-catalog")
__version__: Final[VersionStr] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
VERSION: Final[Version] = info.version
API_VERSION: Final[VersionStr] = info.__version__
API_VTAG: Final[str] = info.api_prefix_path_tag
APP_NAME: Final[str] = info.project_name
SUMMARY: Final[str] = info.get_summary()


# NOTE: https://patorjk.com/software/taag/#p=display&h=0&f=Ogre&t=Catalog
APP_STARTED_BANNER_MSG = r"""
   ___         _           _
  / __\  __ _ | |_   __ _ | |  ___    __ _
 / /    / _` || __| / _` || | / _ \  / _` |
/ /___ | (_| || |_ | (_| || || (_) || (_| |
\____/  \__,_| \__| \__,_||_| \___/  \__, |
                                     |___/     {}
""".format(
    f"v{__version__}"
)


APP_FINISHED_BANNER_MSG = info.get_finished_banner()
