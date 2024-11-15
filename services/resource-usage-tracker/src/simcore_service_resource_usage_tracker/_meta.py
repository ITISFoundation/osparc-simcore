""" Application's metadata

"""

from typing import Final

from models_library.basic_types import VersionStr
from packaging.version import Version
from pydantic import TypeAdapter
from servicelib.utils_meta import PackageInfo
from settings_library.basic_types import VersionTag

info: Final = PackageInfo(package_name="simcore-service-resource-usage-tracker")
__version__: Final[VersionStr] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
VERSION: Final[Version] = info.version
API_VERSION: Final[VersionStr] = info.__version__
API_VTAG: Final[VersionTag] = TypeAdapter(VersionTag).validate_python(
    info.api_prefix_path_tag
)
SUMMARY: Final[str] = info.get_summary()
APP_NAME: Final[str] = PROJECT_NAME

# NOTE: https://texteditor.com/ascii-frames/
APP_STARTED_BANNER_MSG = r"""
d8888b. d88888b .d8888.  .d88b.  db    db d8888b.  .o88b. d88888b        db    db .d8888.  .d8b.   d888b  d88888b        d888888b d8888b.  .d8b.   .o88b. db   dD d88888b d8888b.
88  `8D 88'     88'  YP .8P  Y8. 88    88 88  `8D d8P  Y8 88'            88    88 88'  YP d8' `8b 88' Y8b 88'            `~~88~~' 88  `8D d8' `8b d8P  Y8 88 ,8P' 88'     88  `8D
88oobY' 88ooooo `8bo.   88    88 88    88 88oobY' 8P      88ooooo        88    88 `8bo.   88ooo88 88      88ooooo           88    88oobY' 88ooo88 8P      88,8P   88ooooo 88oobY'
88`8b   88~~~~~   `Y8b. 88    88 88    88 88`8b   8b      88~~~~~ C8888D 88    88   `Y8b. 88~~~88 88  ooo 88~~~~~ C8888D    88    88`8b   88~~~88 8b      88`8b   88~~~~~ 88`8b
88 `88. 88.     db   8D `8b  d8' 88b  d88 88 `88. Y8b  d8 88.            88b  d88 db   8D 88   88 88. ~8~ 88.               88    88 `88. 88   88 Y8b  d8 88 `88. 88.     88 `88.
88   YD Y88888P `8888Y'  `Y88P'  ~Y8888P' 88   YD  `Y88P' Y88888P        ~Y8888P' `8888Y' YP   YP  Y888P  Y88888P           YP    88   YD YP   YP  `Y88P' YP   YD Y88888P 88   YD  {}
""".format(
    f"v{__version__}"
)


APP_FINISHED_BANNER_MSG = info.get_finished_banner()
