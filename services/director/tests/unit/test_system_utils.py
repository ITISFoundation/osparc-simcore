from unittest.mock import mock_open, patch

from simcore_service_director.system_utils import get_system_extra_hosts_raw


# Sample tests
def test_get_system_extra_hosts_raw_with_matching_domain():
    # Simulate the contents of /etc/hosts
    mocked_hosts_content = "127.0.0.1\tlocalhost\n192.168.1.1\texample.com\n"
    extra_host_domain = "example.com"

    with patch("pathlib.Path.open", mock_open(read_data=mocked_hosts_content)), patch(
        "pathlib.Path.exists", return_value=True
    ):
        result = get_system_extra_hosts_raw(extra_host_domain)
        assert result == ["192.168.1.1 example.com"]


def test_get_system_extra_hosts_raw_with_no_matching_domain():
    mocked_hosts_content = "127.0.0.1\tlocalhost\n192.168.1.1\texample.com\n"
    extra_host_domain = "nonexistent.com"

    with patch("pathlib.Path.open", mock_open(read_data=mocked_hosts_content)), patch(
        "pathlib.Path.exists", return_value=True
    ):
        result = get_system_extra_hosts_raw(extra_host_domain)
        assert result == []


def test_get_system_extra_hosts_raw_with_undefined_domain():
    mocked_hosts_content = "127.0.0.1\tlocalhost\n192.168.1.1\texample.com\n"
    extra_host_domain = "undefined"

    with patch("pathlib.Path.open", mock_open(read_data=mocked_hosts_content)), patch(
        "pathlib.Path.exists", return_value=True
    ):
        result = get_system_extra_hosts_raw(extra_host_domain)
        assert result == []


def test_get_system_extra_hosts_raw_with_no_hosts_file():
    extra_host_domain = "example.com"

    with patch("pathlib.Path.exists", return_value=False):
        result = get_system_extra_hosts_raw(extra_host_domain)
        assert result == []
