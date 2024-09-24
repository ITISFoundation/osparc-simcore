import pytest
from service_integration.cli._compose_spec import _strip_credentials


@pytest.mark.parametrize(
    "url, expected_url",
    [
        (
            "schema.veshttps://user:password@example.com/some/repo.git",
            "schema.veshttps://example.com/some/repo.git",
        ),
        (
            "https://user:password@example.com/some/repo.git",
            "https://example.com/some/repo.git",
        ),
        (
            "ssh://user:password@example.com/some/repo.git",
            "ssh://example.com/some/repo.git",
        ),
        (
            "git@git.speag.com:some/repo.git",
            "git@git.speag.com:some/repo.git",
        ),
        ("any_str", "any_str"),
    ],
)
def test__strip_credentials(url: str, expected_url: str):
    assert _strip_credentials(url) == expected_url
