""" Current version of the simcore_service_storage application and its API

"""
import pkg_resources
from semantic_version import Version

__version__: str = pkg_resources.get_distribution("simcore-service-storage").version

version = Version(__version__)

api_version_prefix: str = f"v{version.major}"

app_name: str = __name__.split(".")[0]
api_version: str = __version__
api_vtag: str = f"v{version.major}"

# legacy
api_version_prefix: str = api_vtag


## https://patorjk.com/software/taag/#p=display&f=Standard&t=Storage
WELCOME_MSG = r"""
  ____  _
 / ___|| |_ ___  _ __ __ _  __ _  ___
 \___ \| __/ _ \| '__/ _` |/ _` |/ _ \
  ___) | || (_) | | | (_| | (_| |  __/
 |____/ \__\___/|_|  \__,_|\__, |\___|
                           |___/          {0}

""".format(
    f"v{__version__}"
)
