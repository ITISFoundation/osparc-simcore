"""Application's metadata"""

from typing import Final

import dask
from models_library.basic_types import VersionStr
from servicelib.utils_meta import PackageInfo

info: Final = PackageInfo(package_name="simcore-service-dask-sidecar")
__version__: Final[VersionStr] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
API_VERSION: Final[VersionStr] = info.__version__

# https://patorjk.com/software/taag/#p=display&f=Standard&t=dask%20sidecar
DASK_SIDECAR_APP_STARTED_BANNER_MSG = rf"""

                                       _           _          _     _
   ___  ___ _ __   __ _ _ __ ___    __| | __ _ ___| | __  ___(_) __| | ___  ___ __ _ _ __
  / _ \/ __| '_ \ / _` | '__/ __|  / _` |/ _` / __| |/ / / __| |/ _` |/ _ \/ __/ _` | '__|
 | (_) \__ \ |_) | (_| | | | (__  | (_| | (_| \__ \   <  \__ \ | (_| |  __/ (_| (_| | |
  \___/|___/ .__/ \__,_|_|  \___|  \__,_|\__,_|___/_|\_\ |___/_|\__,_|\___|\___\__,_|_|             v{__version__} with dask=={dask.__version__}
           |_|
"""

DASK_SCHEDULER_APP_STARTED_BANNER_MSG = rf"""

                                       _           _               _              _       _
   ___  ___ _ __   __ _ _ __ ___    __| | __ _ ___| | __  ___  ___| |__   ___  __| |_   _| | ___ _ __
  / _ \/ __| '_ \ / _` | '__/ __|  / _` |/ _` / __| |/ / / __|/ __| '_ \ / _ \/ _` | | | | |/ _ \ '__|
 | (_) \__ \ |_) | (_| | | | (__  | (_| | (_| \__ \   <  \__ \ (__| | | |  __/ (_| | |_| | |  __/ |
  \___/|___/ .__/ \__,_|_|  \___|  \__,_|\__,_|___/_|\_\ |___/\___|_| |_|\___|\__,_|\__,_|_|\___|_|                          v{__version__} with dask=={dask.__version__}
           |_|

"""


def print_dask_sidecar_banner() -> None:
    print(DASK_SIDECAR_APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201


def print_dask_scheduler_banner() -> None:
    print(DASK_SCHEDULER_APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
