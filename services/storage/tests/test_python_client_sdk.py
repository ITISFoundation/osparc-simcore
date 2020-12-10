# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict
import pytest


@pytest.fixture
def search_dict() -> Dict[str, int]:
    return {
        "ClientTimeout(": 0,
        '"HTTP_CLIENT_REQUEST_AIOHTTP_CONNECT_TIMEOUT", "5"': 0,
        '"HTTP_CLIENT_REQUEST_AIOHTTP_SOCK_CONNECT_TIMEOUT", "5"': 0,
    }


def assert_all_hits_found(filled_search_dict: Dict[str, int]) -> None:
    for search_key, value in filled_search_dict.items():
        assert (
            value > 0
        ), f"Could not find an entry for search_key='{search_key}' in storge's python client"


def test_are_settings_present(search_dict, here):
    # scanning all the files in the
    client_sdk_dir = here / ".." / "client-sdk" / "python"
    all_python_files = client_sdk_dir.rglob("*.py")
    for python_file in all_python_files:
        print(f"seaching in file {python_file}")
        for search_hit in search_dict.keys():
            if search_hit in python_file.read_text():
                search_dict[search_hit] += 1

    assert_all_hits_found(search_dict)