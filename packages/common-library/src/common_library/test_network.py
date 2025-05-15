import pytest
from common_library.network import is_ip_address


@pytest.mark.parametrize(
    "host, expected",
    [
        ("127.0.0.1", True),
        ("::1", True),
        ("192.168.1.1", True),
        ("2001:0db8:85a3:0000:0000:8a2e:0370:7334", True),
        ("256.256.256.256", False),
        ("invalid_host", False),
        ("", False),
        ("1234:5678:9abc:def0:1234:5678:9abc:defg", False),
    ],
)
def test_is_ip_address(host: str, expected: bool):
    assert is_ip_address(host) == expected
