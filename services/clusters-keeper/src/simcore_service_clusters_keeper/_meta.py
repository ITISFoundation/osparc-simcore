""" Application's metadata

"""
from contextlib import suppress
from typing import Final

import pkg_resources
from models_library.basic_types import VersionTag
from packaging.version import Version
from pydantic import parse_obj_as

_current_distribution = pkg_resources.get_distribution(
    "simcore-service-clusters_keeper"
)

__version__: str = _current_distribution.version


APP_NAME: Final[str] = _current_distribution.project_name
API_VERSION: Final[str] = __version__
VERSION: Final[Version] = Version(__version__)
API_VTAG: Final[VersionTag] = parse_obj_as(VersionTag, f"v{VERSION.major}")


def get_summary() -> str:
    with suppress(Exception):
        try:
            metadata = _current_distribution.get_metadata_lines("METADATA")
        except FileNotFoundError:
            metadata = _current_distribution.get_metadata_lines("PKG-INFO")

        return next(x.split(":") for x in metadata if x.startswith("Summary:"))[-1]
    return ""


SUMMARY: Final[str] = get_summary()


# https://patorjk.com/software/taag/#p=testall&f=Avatar&t=clusters_keeper
APP_STARTED_BANNER_MSG = r"""

 _______  _                 _______ _________ _______  _______  _______         _        _______  _______  _______  _______  _______
(  ____ \( \      |\     /|(  ____ \\__   __/(  ____ \(  ____ )(  ____ \       | \    /\(  ____ \(  ____ \(  ____ )(  ____ \(  ____ )
| (    \/| (      | )   ( || (    \/   ) (   | (    \/| (    )|| (    \/       |  \  / /| (    \/| (    \/| (    )|| (    \/| (    )|
| |      | |      | |   | || (_____    | |   | (__    | (____)|| (_____        |  (_/ / | (__    | (__    | (____)|| (__    | (____)|
| |      | |      | |   | |(_____  )   | |   |  __)   |     __)(_____  )       |   _ (  |  __)   |  __)   |  _____)|  __)   |     __)
| |      | |      | |   | |      ) |   | |   | (      | (\ (         ) |       |  ( \ \ | (      | (      | (      | (      | (\ (
| (____/\| (____/\| (___) |/\____) |   | |   | (____/\| ) \ \__/\____) |       |  /  \ \| (____/\| (____/\| )      | (____/\| ) \ \__
(_______/(_______/(_______)\_______)   )_(   (_______/|/   \__/\_______) _____ |_/    \/(_______/(_______/|/       (_______/|/   \__/
                                                                        (_____)                                                            {}
""".format(
    f"v{__version__}"
)


APP_FINISHED_BANNER_MSG = "{:=^100}".format(
    f"🎉 App {APP_NAME}=={__version__} shutdown completed 🎉"
)
