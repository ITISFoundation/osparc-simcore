import pytest
from notifications_library._templates import (
    NamedTemplateTuple,
    split_template_name,
)


@pytest.mark.parametrize(
    "template_name,expected",
    [
        (
            "email/paid/body_html.j2",
            NamedTemplateTuple(channel="email", template_name="paid", part="body_html", ext="j2"),
        ),
        (
            "email/registered/subject.j2",
            NamedTemplateTuple(channel="email", template_name="registered", part="subject", ext="j2"),
        ),
    ],
)
def test_split_template_name(template_name: str, expected: NamedTemplateTuple):
    assert split_template_name(template_name) == expected


@pytest.mark.parametrize(
    "invalid_template_name",
    [
        "email/paid",
        "email",
        "email/paid/body_html/extra.j2",
    ],
)
def test_split_template_name_raises_on_invalid(invalid_template_name: str):
    with pytest.raises(TypeError):
        split_template_name(invalid_template_name)

    with pytest.raises(TypeError):
        split_template_name("base.html")
