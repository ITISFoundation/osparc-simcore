"""Application's metadata"""

from typing import Final

from models_library.basic_types import VersionStr
from packaging.version import Version
from servicelib.utils_meta import PackageInfo

info: Final = PackageInfo(package_name="simcore-service-payments")
__version__: Final[VersionStr] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
VERSION: Final[Version] = info.version
API_VERSION: Final[VersionStr] = info.__version__
APP_NAME: Final[str] = info.app_name
API_VTAG: Final[str] = info.api_prefix_path_tag
SUMMARY: Final[str] = info.get_summary()


# NOTE: https://patorjk.com/software/taag/#p=testall&f=Standard&t=Payments
APP_STARTED_BANNER_MSG = r"""
 ____   __   _  _  _  _  ____  __ _  ____  ___
(  _ \ / _\ ( \/ )( \/ )(  __)(  ( \(_  _)/ ___)
 ) __//    \ )  / / \/ \ ) _) /    /  )(  \___ \
(__)  \_/\_/(__/  \_)(_/(____)\_)__) (__) (____/  {}
""".format(
    f"v{__version__}"
)


APP_FINISHED_BANNER_MSG = info.get_finished_banner()
