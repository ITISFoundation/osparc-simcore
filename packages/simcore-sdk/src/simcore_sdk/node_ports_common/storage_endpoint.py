from functools import lru_cache

from aiohttp import encode_basic_auth, hdrs
from settings_library.node_ports import NodePortsSettings


@lru_cache
def is_storage_secure() -> bool:
    settings = NodePortsSettings.create_from_envs()
    node_ports_storage_auth = settings.NODE_PORTS_STORAGE_AUTH
    is_secure: bool = node_ports_storage_auth.STORAGE_SECURE
    return is_secure


@lru_cache
def get_base_url() -> str:
    settings = NodePortsSettings.create_from_envs()
    # pylint:disable=no-member
    base_url: str = settings.NODE_PORTS_STORAGE_AUTH.api_base_url
    return base_url


@lru_cache
def get_basic_auth_headers() -> dict[str, str]:
    """HTTP Basic auth headers for the storage service (empty when auth is not required)"""
    settings = NodePortsSettings.create_from_envs()
    node_ports_storage_auth = settings.NODE_PORTS_STORAGE_AUTH

    if node_ports_storage_auth.auth_required:
        assert node_ports_storage_auth.STORAGE_USERNAME is not None  # nosec
        assert node_ports_storage_auth.STORAGE_PASSWORD is not None  # nosec
        return {
            hdrs.AUTHORIZATION: encode_basic_auth(
                login=node_ports_storage_auth.STORAGE_USERNAME,
                password=node_ports_storage_auth.STORAGE_PASSWORD.get_secret_value(),
            )
        }
    return {}
