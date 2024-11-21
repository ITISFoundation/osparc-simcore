""" Application's metadata

"""

from importlib.metadata import distribution, version
from importlib.resources import files
from pathlib import Path
from typing import Final

from models_library.basic_types import VersionStr, VersionTag
from packaging.version import Version
from pydantic import TypeAdapter

_current_distribution = distribution("simcore-service-efs-guardian")
__version__: str = version("simcore-service-efs-guardian")


APP_NAME: Final[str] = _current_distribution.metadata["Name"]
API_VERSION: Final[VersionStr] = TypeAdapter(VersionStr).validate_python(__version__)
VERSION: Final[Version] = Version(__version__)
API_VTAG: Final[VersionTag] = TypeAdapter(VersionTag).validate_python(
    f"v{VERSION.major}"
)
RPC_VTAG: Final[VersionTag] = TypeAdapter(VersionTag).validate_python(
    f"v{VERSION.major}"
)


def get_summary() -> str:
    return _current_distribution.metadata.get_all("Summary", [""])[-1]


SUMMARY: Final[str] = get_summary()
PACKAGE_DATA_FOLDER: Final[Path] = Path(f'{files(APP_NAME.replace("-", "_")) / "data"}')

# https://patorjk.com/software/taag/#p=display&f=ANSI%20Shadow&t=Elastic%20file%0Asystem%20guardian
APP_STARTED_BANNER_MSG = r"""
███████╗██╗      █████╗ ███████╗████████╗██╗ ██████╗    ███████╗██╗██╗     ███████╗
██╔════╝██║     ██╔══██╗██╔════╝╚══██╔══╝██║██╔════╝    ██╔════╝██║██║     ██╔════╝
█████╗  ██║     ███████║███████╗   ██║   ██║██║         █████╗  ██║██║     █████╗
██╔══╝  ██║     ██╔══██║╚════██║   ██║   ██║██║         ██╔══╝  ██║██║     ██╔══╝
███████╗███████╗██║  ██║███████║   ██║   ██║╚██████╗    ██║     ██║███████╗███████╗
╚══════╝╚══════╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝ ╚═════╝    ╚═╝     ╚═╝╚══════╝╚══════╝

███████╗██╗   ██╗███████╗████████╗███████╗███╗   ███╗     ██████╗ ██╗   ██╗ █████╗ ██████╗ ██████╗ ██╗ █████╗ ███╗   ██╗
██╔════╝╚██╗ ██╔╝██╔════╝╚══██╔══╝██╔════╝████╗ ████║    ██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔══██╗██║██╔══██╗████╗  ██║
███████╗ ╚████╔╝ ███████╗   ██║   █████╗  ██╔████╔██║    ██║  ███╗██║   ██║███████║██████╔╝██║  ██║██║███████║██╔██╗ ██║
╚════██║  ╚██╔╝  ╚════██║   ██║   ██╔══╝  ██║╚██╔╝██║    ██║   ██║██║   ██║██╔══██║██╔══██╗██║  ██║██║██╔══██║██║╚██╗██║
███████║   ██║   ███████║   ██║   ███████╗██║ ╚═╝ ██║    ╚██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝██║██║  ██║██║ ╚████║
╚══════╝   ╚═╝   ╚══════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝     ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝
                          🛡️ Welcome to EFS-Guardian App 🛡️
                       Your Elastic File System Manager & Monitor
                                                                                                                        {}
""".format(
    f"v{__version__}"
)

APP_STARTED_DISABLED_BANNER_MSG = r"""
██████╗ ██╗███████╗ █████╗ ██████╗ ██╗     ███████╗██████╗
██╔══██╗██║██╔════╝██╔══██╗██╔══██╗██║     ██╔════╝██╔══██╗
██║  ██║██║███████╗███████║██████╔╝██║     █████╗  ██║  ██║
██║  ██║██║╚════██║██╔══██║██╔══██╗██║     ██╔══╝  ██║  ██║
██████╔╝██║███████║██║  ██║██████╔╝███████╗███████╗██████╔╝
╚═════╝ ╚═╝╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝╚═════╝
"""

APP_FINISHED_BANNER_MSG = "{:=^100}".format(
    f"🎉 App {APP_NAME}=={__version__} shutdown completed 🎉"
)
