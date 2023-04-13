""" Application's metadata

"""
from typing import Final

from packaging.version import Version
from pydantic import parse_obj_as
from servicelib.utils_meta import PackageInfo

from .models.schemas.meta import VersionStr

info: Final = PackageInfo(package_name="simcore-service-director-v2")
__version__: Final[str] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
VERSION: Final[Version] = info.version
API_VERSION: Final[VersionStr] = parse_obj_as(VersionStr, info.__version__)
API_VTAG: Final[str] = info.api_prefix_path_tag
SUMMARY: Final[str] = info.get_summary()
