""" Package Metadata

"""
import pkg_resources

current_distribution = pkg_resources.get_distribution("simcore_service_director_v2")

project_name: str = current_distribution.project_name

api_version: str = current_distribution.version
major, minor, patch = current_distribution.version.split(".")
api_vtag: str = f"v{major}"

__version__ = current_distribution.version

summary: str = next(
    x.split(":")
    for x in current_distribution.get_metadata_lines("PKG-INFO")
    if x.startswith("Summary:")
)[-1]

WELCOME_MSG = r"""
______ _               _
|  _  (_)             | |
| | | |_ _ __ ___  ___| |_ ___  _ __
| | | | | '__/ _ \/ __| __/ _ \| '__|
| |/ /| | | |  __/ (__| || (_) | |
|___/ |_|_|  \___|\___|\__\___/|_|   {0}

""".format(f"v{__version__}")
