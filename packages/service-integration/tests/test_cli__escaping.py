import pytest
from service_integration.cli._escaping import escape_dollar_brace


@pytest.mark.parametrize(
    "to_escape, escaped",
    [
        ("some text", "some text"),
        ("$${escapes}", "$$$${escapes}"),
        ("$$${preserves}", "$$${preserves}"),
        ("$$$${preserves}", "$$$${preserves}"),
        ("$$$$${preserves}", "$$$$${preserves}"),
        (
            "$${escapes} & $$${preserves},$$$${preserves}, $$$$${preserves}",
            "$$$${escapes} & $$${preserves},$$$${preserves}, $$$$${preserves}",
        ),
    ],
)
def test_escape_dollar_brace(to_escape: str, escaped: str):
    assert escape_dollar_brace(to_escape) == escaped
