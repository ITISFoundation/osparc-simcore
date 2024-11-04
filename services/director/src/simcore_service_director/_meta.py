""" Application's metadata

"""

from typing import Final

from models_library.basic_types import VersionStr, VersionTag
from packaging.version import Version
from servicelib.utils_meta import PackageInfo

info: Final = PackageInfo(package_name="simcore-service-director")
__version__: Final[VersionStr] = info.__version__


PROJECT_NAME: Final[str] = info.project_name
VERSION: Final[Version] = info.version
API_VERSION: Final[VersionStr] = info.__version__
APP_NAME: Final[str] = PROJECT_NAME
API_VTAG: Final[VersionTag] = VersionTag(info.api_prefix_path_tag)
SUMMARY: Final[str] = info.get_summary()


# NOTE: https://patorjk.com/software/taag/#p=display&f=Electronic&t=Director-v0
APP_STARTED_BANNER_MSG = r"""

 ▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄           ▄               ▄  ▄▄▄▄▄▄▄▄▄
▐░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌         ▐░▌             ▐░▌▐░░░░░░░░░▌
▐░█▀▀▀▀▀▀▀█░▌▀▀▀▀█░█▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀▀▀▀▀▀  ▀▀▀▀█░█▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀█░▌          ▐░▌           ▐░▌▐░█░█▀▀▀▀▀█░▌
▐░▌       ▐░▌    ▐░▌     ▐░▌       ▐░▌▐░▌          ▐░▌               ▐░▌     ▐░▌       ▐░▌▐░▌       ▐░▌           ▐░▌         ▐░▌ ▐░▌▐░▌    ▐░▌
▐░▌       ▐░▌    ▐░▌     ▐░█▄▄▄▄▄▄▄█░▌▐░█▄▄▄▄▄▄▄▄▄ ▐░▌               ▐░▌     ▐░▌       ▐░▌▐░█▄▄▄▄▄▄▄█░▌ ▄▄▄▄▄▄▄▄▄▄▄▐░▌       ▐░▌  ▐░▌ ▐░▌   ▐░▌
▐░▌       ▐░▌    ▐░▌     ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░▌               ▐░▌     ▐░▌       ▐░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░▌     ▐░▌   ▐░▌  ▐░▌  ▐░▌
▐░▌       ▐░▌    ▐░▌     ▐░█▀▀▀▀█░█▀▀ ▐░█▀▀▀▀▀▀▀▀▀ ▐░▌               ▐░▌     ▐░▌       ▐░▌▐░█▀▀▀▀█░█▀▀  ▀▀▀▀▀▀▀▀▀▀▀  ▐░▌   ▐░▌    ▐░▌   ▐░▌ ▐░▌
▐░▌       ▐░▌    ▐░▌     ▐░▌     ▐░▌  ▐░▌          ▐░▌               ▐░▌     ▐░▌       ▐░▌▐░▌     ▐░▌                 ▐░▌ ▐░▌     ▐░▌    ▐░▌▐░▌
▐░█▄▄▄▄▄▄▄█░▌▄▄▄▄█░█▄▄▄▄ ▐░▌      ▐░▌ ▐░█▄▄▄▄▄▄▄▄▄ ▐░█▄▄▄▄▄▄▄▄▄      ▐░▌     ▐░█▄▄▄▄▄▄▄█░▌▐░▌      ▐░▌                 ▐░▐░▌      ▐░█▄▄▄▄▄█░█░▌
▐░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░▌       ▐░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌     ▐░▌     ▐░░░░░░░░░░░▌▐░▌       ▐░▌                 ▐░▌        ▐░░░░░░░░░▌
 ▀▀▀▀▀▀▀▀▀▀  ▀▀▀▀▀▀▀▀▀▀▀  ▀         ▀  ▀▀▀▀▀▀▀▀▀▀▀  ▀▀▀▀▀▀▀▀▀▀▀       ▀       ▀▀▀▀▀▀▀▀▀▀▀  ▀         ▀                   ▀          ▀▀▀▀▀▀▀▀▀
                                                                                                                                                 {}
""".format(
    f"v{__version__}"
)


APP_FINISHED_BANNER_MSG = info.get_finished_banner()
