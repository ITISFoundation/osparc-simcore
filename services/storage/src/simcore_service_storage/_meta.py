from typing import Final

from models_library.basic_types import VersionStr
from packaging.version import Version
from servicelib.utils_meta import PackageInfo

info: Final = PackageInfo(package_name="simcore-service-storage")
__version__: Final[VersionStr] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
VERSION: Final[Version] = info.version
API_VERSION: Final[VersionStr] = info.__version__
API_VTAG: Final[str] = info.api_prefix_path_tag
SUMMARY: Final[str] = info.get_summary()
APP_NAME: Final[str] = info.app_name

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

APP_WORKER_STARTED_BANNER_MSG = r"""

  ____  _                                __        __         _
 / ___|| |_ ___  _ __ __ _  __ _  ___    \ \      / /__  _ __| | _____ _ __
 \___ \| __/ _ \| '__/ _` |/ _` |/ _ \____\ \ /\ / / _ \| '__| |/ / _ \ '__|
  ___) | || (_) | | | (_| | (_| |  __/_____\ V  V / (_) | |  |   <  __/ |
 |____/ \__\___/|_|  \__,_|\__, |\___|      \_/\_/ \___/|_|  |_|\_\___|_|
                           |___/                                                {}

""".format(
    f"v{__version__}"
)

APP_FINISHED_BANNER_MSG = info.get_finished_banner()
