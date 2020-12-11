# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict
import pytest

TEMPLATE_CODE_NEEDED_HINT = """
-------------------------

import os

def get_http_client_request_aiohttp_connect_timeout() -> int:
    return int(os.environ.get("HTTP_CLIENT_REQUEST_AIOHTTP_CONNECT_TIMEOUT", "5"))


def get_http_client_request_aiohttp_sock_connect_timeout() -> int:
    return int(os.environ.get("HTTP_CLIENT_REQUEST_AIOHTTP_SOCK_CONNECT_TIMEOUT", "5"))


class RESTClientObject(object):

    def __init__(self, configuration, pools_size=4, maxsize=4):
        
        ...

        # We are interested in fast connections, if a connection is established
        # there is no timeout for file download operations
        timeout = aiohttp.ClientTimeout(
            total=None, 
            connect=get_http_client_request_aiohttp_connect_timeout(), 
            sock_connect=get_http_client_request_aiohttp_sock_connect_timeout(),
        )
        if configuration.proxy:
            self.pool_manager = aiohttp.ClientSession(
                connector=connector,
                proxy=configuration.proxy,
                timeout=timeout,
            )
        else:
            self.pool_manager = aiohttp.ClientSession(
                connector=connector, timeout=timeout
            )

-------------------------
"""


@pytest.fixture
def search_dict() -> Dict[str, int]:
    return {
        "import os": 0,
        "timeout=timeout": 0,
        '"HTTP_CLIENT_REQUEST_AIOHTTP_CONNECT_TIMEOUT", "5"': 0,
        '"HTTP_CLIENT_REQUEST_AIOHTTP_SOCK_CONNECT_TIMEOUT", "5"': 0,
    }


def assert_all_hits_found(filled_search_dict: Dict[str, int], file_path: str) -> None:
    for search_key, value in filled_search_dict.items():
        message = (
            f"Could not find an entry for search_key='{search_key}' in "
            "storage's python client.\nMake sure something similar like below "
            f"is present in '{file_path}'\n{TEMPLATE_CODE_NEEDED_HINT}"
        )
        assert value > 0, message


def test_are_settings_present(search_dict, here):
    # scanning all the files in the
    client_sdk_dir = here / ".." / "client-sdk" / "python"
    all_python_files = client_sdk_dir.rglob("*.py")
    for python_file in all_python_files:
        print(f"seaching in file {python_file}")
        for search_hit in search_dict.keys():
            if search_hit in python_file.read_text():
                search_dict[search_hit] += 1

    assert_all_hits_found(search_dict, str(client_sdk_dir))