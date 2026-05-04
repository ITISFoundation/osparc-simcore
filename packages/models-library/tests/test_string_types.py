# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from models_library.string_types import (
    _SHORT_TRUNCATED_STR_MAX_LENGTH,
    DescriptionSafeStr,
    NameSafeStr,
    ShortTruncatedStr,
)
from pydantic import BaseModel, TypeAdapter, ValidationError


def test_short_truncated_string():
    curtail_length = _SHORT_TRUNCATED_STR_MAX_LENGTH
    assert TypeAdapter(ShortTruncatedStr).validate_python("X" * curtail_length) == "X" * curtail_length, (
        "Max length string should remain intact"
    )

    assert TypeAdapter(ShortTruncatedStr).validate_python("X" * (curtail_length + 1)) == "X" * curtail_length, (
        "Overlong string should be truncated exactly to max length"
    )

    assert TypeAdapter(ShortTruncatedStr).validate_python("X" * (curtail_length + 100)) == "X" * curtail_length, (
        "Much longer string should still truncate to exact max length"
    )

    # below limit
    assert TypeAdapter(ShortTruncatedStr).validate_python("X" * (curtail_length - 1)) == "X" * (curtail_length - 1), (
        "Under-length string should not be modified"
    )

    # spaces are trimmed
    assert TypeAdapter(ShortTruncatedStr).validate_python(" " * (curtail_length + 1)) == "", (
        "Only-whitespace string should become empty string"
    )


class InputRequestModel(BaseModel):
    name: NameSafeStr
    description: DescriptionSafeStr


@pytest.mark.parametrize(
    "name,description,should_pass",
    [
        # ✅ valid inputs
        pytest.param("Alice", "Simple markdown **text**.", True, id="valid-alice"),
        pytest.param("ACME_Inc", "Multi-line\nMarkdown _description_.", True, id="valid-acme"),
        pytest.param("John-Doe", "Has some <b>inline HTML</b>.", True, id="valid-html-inline"),
        # ❌ unsafe / invalid names
        pytest.param("<script>", "valid description", False, id="invalid-name-script"),
        pytest.param("", "short", False, id="invalid-name-empty"),
        pytest.param("A" * 200, "too long name", False, id="invalid-name-too-long"),
        # ❌ unsafe / invalid descriptions
        pytest.param("SafeName", "<script>alert(1)</script>", False, id="invalid-desc-script"),
        pytest.param("SafeName", "  ", False, id="invalid-desc-whitespace"),
        pytest.param("SafeName", "a" * 6000, False, id="invalid-desc-too-long"),
        # ❌ additional JS injection patterns that should be caught
        pytest.param(
            "SafeName",
            "<iframe src='javascript:alert(1)'></iframe>",
            False,
            id="invalid-desc-iframe",
        ),
        pytest.param(
            "SafeName",
            "<img onerror='alert(1)' src='x'>",
            False,
            id="invalid-desc-img-onerror",
        ),
        pytest.param(
            "SafeName",
            "<svg onload='alert(1)'></svg>",
            False,
            id="invalid-desc-svg-onload",
        ),
        pytest.param("SafeName", "vbscript:msgbox(1)", False, id="invalid-desc-vbscript"),
        pytest.param("SafeName", "&#106;avascript:alert(1)", False, id="invalid-desc-encoded-js"),
        # ❌ ReDoS (Regular expression Denial of Service) test patterns
        pytest.param(
            "SafeName",
            "<script" + " " * 200 + ">alert(1)</script>",
            False,
            id="redos-script-spaces",
        ),
        pytest.param(
            "SafeName",
            "<img" + " src='x'" * 100 + " onerror='alert(1)'>",
            False,
            id="redos-img-attributes",
        ),
        # ❌ Obfuscated protocol tests
        pytest.param(
            "SafeName",
            "j a v a s c r i p t:alert(1)",
            False,
            id="invalid-desc-spaced-js",
        ),
        pytest.param(
            "SafeName",
            "java\nscript\t:alert(1)",
            False,
            id="invalid-desc-newline-js",
        ),
        pytest.param(
            "SafeName",
            "d\ta\tt\ta:text/html,<script>alert(1)</script>",
            False,
            id="invalid-desc-obfuscated-data",
        ),
        pytest.param(
            "SafeName",
            "v b\ts c r i p t:MsgBox(1)",
            False,
            id="invalid-desc-spaced-vbs",
        ),
    ],
)
def test_safe_string_types(name: str, description: str, should_pass: bool):
    if should_pass:
        model = InputRequestModel(name=name, description=description)
        assert model.name
        assert model.description
    else:
        with pytest.raises(ValidationError) as exc_info:
            InputRequestModel(name=name, description=description)

        assert exc_info.value.error_count() in (1, 2)

        for error in exc_info.value.errors():
            assert error["loc"][0] in ("name", "description")
            assert error["type"] in (
                # NOTE: these codes could be used by the front-end if needed
                "string_pattern_mismatch",
                "string_unsafe_content",
                "string_too_short",
                "string_too_long",
            ), error["msg"]
