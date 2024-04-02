from typing import Final

from packaging.version import Version
from servicelib.utils_meta import PackageInfo

info: Final = PackageInfo(package_name="simcore-service-storage")
__version__: Final[str] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
VERSION: Final[Version] = info.version
API_VERSION: Final[str] = info.__version__
API_VTAG: Final[str] = info.api_prefix_path_tag
SUMMARY: Final[str] = info.get_summary()


## https://patorjk.com/software/taag/#p=display&f=Standard&t=Storage
APP_STARTED_BANNER_MSG = r"""
  ____  _
 / ___|| |_ ___  _ __ __ _  __ _  ___
 \___ \| __/ _ \| '__/ _` |/ _` |/ _ \
  ___) | || (_) | | | (_| | (_| |  __/
 |____/ \__\___/|_|  \__,_|\__, |\___|
                           |___/          {}

""".format(
    f"v{__version__}"
)
