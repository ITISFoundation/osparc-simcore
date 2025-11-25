import pytest
from common_library.network import is_ip_address, redact_url


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


@pytest.mark.parametrize(
    "url, expected",
    [
        # URLs without password - should remain unchanged
        ("https://example.com", "https://example.com"),
        ("http://localhost:8080", "http://localhost:8080"),
        ("https://user@example.com", "https://user@example.com"),
        ("ftp://example.com/path", "ftp://example.com/path"),
        (
            "https://example.com/path?query=value",
            "https://example.com/path?query=value",
        ),
        ("https://example.com/path#fragment", "https://example.com/path#fragment"),
        # URLs with password - should be redacted
        ("https://user:password@example.com", "https://user:***@example.com"),
        ("http://user:secret123@localhost:8080", "http://user:***@localhost:8080"),
        (
            "postgres://user:pass@db.example.com:5432/database",
            "postgres://user:***@db.example.com:5432/database",
        ),
        (
            "https://admin:supersecret@api.example.com/v1/endpoint",
            "https://admin:***@api.example.com/v1/endpoint",
        ),
        (
            "ftp://user:pwd@ftp.example.com/files",
            "ftp://user:***@ftp.example.com/files",
        ),
        ("amqp://admin:mysecret@rabbit:5672", "amqp://admin:***@rabbit:5672"),
        ("redis://:adminadmin@redis:6379/3", "redis://:***@redis:6379/3"),
        # URLs with password and query/fragment
        (
            "https://user:pass@example.com/path?query=value",
            "https://user:***@example.com/path?query=value",
        ),
        (
            "https://user:pass@example.com/path#fragment",
            "https://user:***@example.com/path#fragment",
        ),
        (
            "https://user:pass@example.com/path?query=value#fragment",
            "https://user:***@example.com/path?query=value#fragment",
        ),
        # URLs with password but no username (edge case)
        ("https://:password@example.com", "https://:***@example.com"),
        # URLs with special characters in password
        ("https://user:p@ss%40word@example.com", "https://user:***@example.com"),
        ("https://user:p:a:s:s@example.com", "https://user:***@example.com"),
        # Empty URL
        ("", ""),
        # Invalid URLs (should not crash)
        ("not-a-url", "not-a-url"),
    ],
)
def test_redact_url(url: str, expected: str):
    assert redact_url(url) == expected
