""" Application's metadata

"""


from typing import Final

import dask
from servicelib.utils_meta import PackageInfo

info: Final = PackageInfo(package_name="simcore_service_dask_sidecar")
__version__: Final[str] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
API_VERSION: Final[str] = info.__version__

# https://patorjk.com/software/taag/#p=display&f=Standard&t=dask%20sidecar
APP_STARTED_BANNER_MSG = rf"""
      _           _          _     _
   __| | __ _ ___| | __  ___(_) __| | ___  ___ __ _ _ __
  / _` |/ _` / __| |/ / / __| |/ _` |/ _ \/ __/ _` | '__|
 | (_| | (_| \__ \   <  \__ \ | (_| |  __/ (_| (_| | |
  \__,_|\__,_|___/_|\_\ |___/_|\__,_|\___|\___\__,_|_|    v{__version__} with dask=={dask.__version__}

"""


def print_banner() -> None:
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
