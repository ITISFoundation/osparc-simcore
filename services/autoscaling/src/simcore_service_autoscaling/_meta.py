from typing import Final

from models_library.basic_types import VersionStr, VersionTag
from packaging.version import Version
from pydantic import TypeAdapter
from servicelib.utils_meta import PackageInfo

info: Final = PackageInfo(package_name="simcore-service-autoscaling")
__version__: Final[VersionStr] = info.__version__

APP_NAME: Final[str] = info.project_name
API_VERSION: Final[VersionStr] = info.__version__
VERSION: Final[Version] = info.version
API_VTAG: Final[VersionTag] = TypeAdapter(VersionTag).validate_python(
    info.api_prefix_path_tag
)
SUMMARY: Final[str] = info.get_summary()


# https://patorjk.com/software/taag/#p=testall&f=Avatar&t=Autoscaling
APP_STARTED_BANNER_MSG = r"""
                _                      _ _
     /\        | |                    | (_)
    /  \  _   _| |_ ___  ___  ___ __ _| |_ _ __   __ _
   / /\ \| | | | __/ _ \/ __|/ __/ _` | | | '_ \ / _` |
  / ____ \ |_| | || (_) \__ \ (_| (_| | | | | | | (_| |
 /_/    \_\__,_|\__\___/|___/\___\__,_|_|_|_| |_|\__, |
                                                  __/ |
                                                 |___/       {}
""".format(
    f"v{__version__}"
)

APP_STARTED_COMPUTATIONAL_BANNER_MSG = r"""
                                       _          _    _                       _
                                      | |        | |  (_)                     | |
   ___  ___   _ __ ___   _ __   _   _ | |_  __ _ | |_  _   ___   _ __    __ _ | |
  / __|/ _ \ | '_ ` _ \ | '_ \ | | | || __|/ _` || __|| | / _ \ | '_ \  / _` || |
 | (__| (_) || | | | | || |_) || |_| || |_| (_| || |_ | || (_) || | | || (_| || |
  \___|\___/ |_| |_| |_|| .__/  \__,_| \__|\__,_| \__||_| \___/ |_| |_| \__,_||_|
                        | |
                        |_|
"""

APP_STARTED_DYNAMIC_BANNER_MSG = r"""
      _                                  _
     | |                                (_)
   __| | _   _  _ __    __ _  _ __ ___   _   ___
  / _` || | | || '_ \  / _` || '_ ` _ \ | | / __|
 | (_| || |_| || | | || (_| || | | | | || || (__
  \__,_| \__, ||_| |_| \__,_||_| |_| |_||_| \___|
          __/ |
         |___/
"""

APP_STARTED_DISABLED_BANNER_MSG = r"""
      _  _              _      _            _
     | |(_)            | |    | |          | |
   __| | _  ___   __ _ | |__  | |  ___   __| |
  / _` || |/ __| / _` || '_ \ | | / _ \ / _` |
 | (_| || |\__ \| (_| || |_) || ||  __/| (_| |
  \__,_||_||___/ \__,_||_.__/ |_| \___| \__,_|
"""

APP_FINISHED_BANNER_MSG = info.get_finished_banner()
