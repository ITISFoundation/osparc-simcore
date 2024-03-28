""" Current version of the simcore_service_storage application and its API

"""

from importlib.metadata import version

from semantic_version import Version

__version__: str = version("simcore-service-storage")

version_info = Version(__version__)
assert version_info.major is not None  # nosec
api_version_prefix: str = f"v{version_info.major}"

app_name: str = __name__.split(".")[0]
api_version: str = __version__
api_vtag: str = f"v{version_info.major}"


## https://patorjk.com/software/taag/#p=display&f=Standard&t=Storage
WELCOME_MSG = r"""
  ____  _
 / ___|| |_ ___  _ __ __ _  __ _  ___
 \___ \| __/ _ \| '__/ _` |/ _` |/ _ \
  ___) | || (_) | | | (_| | (_| |  __/
 |____/ \__\___/|_|  \__,_|\__, |\___|
                           |___/          {}

""".format(
    f"v{__version__}"
)
