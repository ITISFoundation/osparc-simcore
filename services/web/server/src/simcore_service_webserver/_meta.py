"""Current version of the simcore_service_webserver application and its API"""

from typing import Final

from models_library.basic_types import VersionStr
from packaging.version import Version
from servicelib.utils_meta import PackageInfo

info: Final = PackageInfo(package_name="simcore-service-webserver")
__version__: Final[VersionStr] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
VERSION: Final[Version] = info.version
API_VERSION: Final[VersionStr] = info.__version__
API_VTAG: Final[str] = info.api_prefix_path_tag
SUMMARY: Final[str] = info.get_summary()


# legacy consts
APP_NAME: Final[str] = info.app_name
PROMETHEUS_FRIENDLY_APP_NAME: Final[str] = info.prometheus_friendly_app_name
api_version_prefix: str = API_VTAG


WELCOME_MSG = r"""
 _    _        _
| |  | |      | |
| |  | |  ___ | |__   ___   ___  _ __ __   __ ___  _ __
| |/\| | / _ \| '_ \ / __| / _ \| '__|\ \ / // _ \| '__|
\  /\  /|  __/| |_) |\__ \|  __/| |    \ V /|  __/| |
 \/  \/  \___||_.__/ |___/ \___||_|     \_/  \___||_|     {}
""".format(
    f"v{__version__}"
)

# SEE: https://patorjk.com/software/taag/#p=display&f=Fire%20Font-s&t=GC
WELCOME_GC_MSG = r"""
    (        (
    )\ )     )\
   (()/(   (((_)
    /(_))_ )\___
   (_)) __((/ __|
     | (_ || (__
      \___| \___|

"""

WELCOME_DB_LISTENER_MSG = r"""

 _____ _____     ____  ___ _____ ____ _____ _____ _____ _____
|  _  /  _  \___/  _/ /___/  ___/    /   __/  _  /   __/  _  \
|  |  |  _  <___|  |--|   |___  \-  -|   __|  |  |   __|  _  <
|_____\_____/   \_____\___<_____/|__|\_____\__|__\_____\__|\_/

"""

# SEE https://patorjk.com/software/taag/#p=display&f=BlurVision%20ASCII&t=Auth%0A
WELCOME_AUTH_APP_MSG = r"""
 ░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░
░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓████████▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░   ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░    {}
""".format(
    f"v{__version__}"
)
