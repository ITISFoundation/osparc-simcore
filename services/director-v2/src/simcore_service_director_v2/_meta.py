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
