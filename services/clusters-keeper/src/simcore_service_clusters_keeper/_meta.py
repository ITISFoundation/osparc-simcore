""" Application's metadata

"""

from importlib.metadata import distribution, version
from importlib.resources import files
from pathlib import Path
from typing import Final

from models_library.basic_types import VersionStr, VersionTag
from packaging.version import Version
from pydantic import TypeAdapter

_current_distribution = distribution("simcore-service-clusters-keeper")
__version__: str = version("simcore-service-clusters-keeper")


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

# https://patorjk.com/software/taag/#p=testall&f=Avatar&t=clusters_keeper
APP_STARTED_BANNER_MSG = r"""

 _______  _                 _______ _________ _______  _______  _______         _        _______  _______  _______  _______  _______
(  ____ \( \      |\     /|(  ____ \\__   __/(  ____ \(  ____ )(  ____ \       | \    /\(  ____ \(  ____ \(  ____ )(  ____ \(  ____ )
| (    \/| (      | )   ( || (    \/   ) (   | (    \/| (    )|| (    \/       |  \  / /| (    \/| (    \/| (    )|| (    \/| (    )|
| |      | |      | |   | || (_____    | |   | (__    | (____)|| (_____  _____ |  (_/ / | (__    | (__    | (____)|| (__    | (____)|
| |      | |      | |   | |(_____  )   | |   |  __)   |     __)(_____  )(_____)|   _ (  |  __)   |  __)   |  _____)|  __)   |     __)
| |      | |      | |   | |      ) |   | |   | (      | (\ (         ) |       |  ( \ \ | (      | (      | (      | (      | (\ (
| (____/\| (____/\| (___) |/\____) |   | |   | (____/\| ) \ \__/\____) |       |  /  \ \| (____/\| (____/\| )      | (____/\| ) \ \__
(_______/(_______/(_______)\_______)   )_(   (_______/|/   \__/\_______)       |_/    \/(_______/(_______/|/       (_______/|/   \__/
                                                                                                                                    {}
""".format(
    f"v{__version__}"
)

APP_STARTED_DISABLED_BANNER_MSG = r"""
      _  _              _      _            _
     | |(_)            | |    | |          | |
   __| | _  ___   __ _ | |__  | |  ___   __| |
  / _` || |/ __| / _` || '_ \ | | / _ \ / _` |
 | (_| || |\__ \| (_| || |_) || ||  __/| (_| |
  \__,_||_||___/ \__,_||_.__/ |_| \___| \__,_|
"""

APP_FINISHED_BANNER_MSG = "{:=^100}".format(
    f"🎉 App {APP_NAME}=={__version__} shutdown completed 🎉"
)
