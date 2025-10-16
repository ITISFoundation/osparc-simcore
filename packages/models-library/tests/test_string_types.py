from models_library.basic_types import (
    _SHORT_TRUNCATED_STR_MAX_LENGTH,
)
from models_library.string_types import ShortTruncatedStr
from pydantic import TypeAdapter


def test_short_truncated_string():
    curtail_length = _SHORT_TRUNCATED_STR_MAX_LENGTH
    assert (
        TypeAdapter(ShortTruncatedStr).validate_python("X" * curtail_length)
        == "X" * curtail_length
    ), "Max length string should remain intact"

    assert (
        TypeAdapter(ShortTruncatedStr).validate_python("X" * (curtail_length + 1))
        == "X" * curtail_length
    ), "Overlong string should be truncated exactly to max length"

    assert (
        TypeAdapter(ShortTruncatedStr).validate_python("X" * (curtail_length + 100))
        == "X" * curtail_length
    ), "Much longer string should still truncate to exact max length"

    # below limit
    assert TypeAdapter(ShortTruncatedStr).validate_python(
        "X" * (curtail_length - 1)
    ) == "X" * (curtail_length - 1), "Under-length string should not be modified"

    # spaces are trimmed
    assert (
        TypeAdapter(ShortTruncatedStr).validate_python(" " * (curtail_length + 1)) == ""
    ), "Only-whitespace string should become empty string"
