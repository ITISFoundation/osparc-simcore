from contextlib import suppress

import dask
import pkg_resources

current_distribution = pkg_resources.get_distribution("simcore_service_dask_sidecar")

project_name: str = current_distribution.project_name

api_version: str = current_distribution.version
major, minor, patch = current_distribution.version.split(".")
api_vtag: str = f"v{major}"

__version__ = current_distribution.version


def get_summary() -> str:
    with suppress(Exception):
        try:
            metadata = current_distribution.get_metadata_lines("METADATA")
        except FileNotFoundError:
            metadata = current_distribution.get_metadata_lines("PKG-INFO")

        return next(x.split(":") for x in metadata if x.startswith("Summary:"))[-1]
    return ""


summary: str = get_summary()


# https://patorjk.com/software/taag/#p=display&f=Standard&t=dask%20sidecar
BANNER_MESSAGE = rf"""
      _           _          _     _
   __| | __ _ ___| | __  ___(_) __| | ___  ___ __ _ _ __
  / _` |/ _` / __| |/ / / __| |/ _` |/ _ \/ __/ _` | '__|
 | (_| | (_| \__ \   <  \__ \ | (_| |  __/ (_| (_| | |
  \__,_|\__,_|___/_|\_\ |___/_|\__,_|\___|\___\__,_|_|    v{__version__} with dask=={dask.__version__}

"""


def print_banner() -> None:
    print(BANNER_MESSAGE, flush=True)
