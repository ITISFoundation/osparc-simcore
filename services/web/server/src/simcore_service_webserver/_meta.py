""" Current version of the simcore_service_webserver application and its API

"""
import pkg_resources
from semantic_version import Version

__version__: str = pkg_resources.get_distribution("simcore-service-webserver").version

version = Version(__version__)

APP_NAME: str = __name__.split(".")[0]
API_VERSION: str = __version__
API_VTAG: str = f"v{version.major}"

# legacy
api_version_prefix: str = API_VTAG


WELCOME_MSG = r"""
 _    _        _
| |  | |      | |
| |  | |  ___ | |__   ___   ___  _ __ __   __ ___  _ __
| |/\| | / _ \| '_ \ / __| / _ \| '__|\ \ / // _ \| '__|
\  /\  /|  __/| |_) |\__ \|  __/| |    \ V /|  __/| |
 \/  \/  \___||_.__/ |___/ \___||_|     \_/  \___||_|     {0}
""".format(
    f"v{__version__}"
)
