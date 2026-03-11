"""WebServer RPC Client Package

Provides a class-based, modular RPC client for webserver services.
"""

from .api_keys import ApiKeysRpcApi
from .client import WebServerRpcClient
from .functions import FunctionsRpcApi
from .licenses import LicensesRpcApi
from .projects import ProjectsRpcApi

__all__: tuple[str, ...] = (
    "ApiKeysRpcApi",
    "FunctionsRpcApi",
    "LicensesRpcApi",
    "ProjectsRpcApi",
    "WebServerRpcClient",
)
