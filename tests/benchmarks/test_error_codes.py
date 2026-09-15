"""Benchmarks for `common_library.error_codes`

Error codes (OEC) are created for every unexpected exception raised in the
platform, i.e. on error paths that must stay cheap even under load.
"""

import pytest
from common_library.error_codes import (
    create_error_code,
    parse_error_code_parts,
    parse_error_codes,
)

_NUM_FRAMES = 12


def _recursive_raise(depth: int) -> None:
    if depth == 0:
        msg = "something went wrong"
        raise RuntimeError(msg)
    _recursive_raise(depth - 1)


@pytest.fixture(scope="module")
def deep_exception() -> BaseException:
    try:
        _recursive_raise(_NUM_FRAMES)
    except RuntimeError as exc:
        return exc
    pytest.fail("expected a RuntimeError")


@pytest.fixture(scope="module")
def log_message(deep_exception: BaseException) -> str:
    codes = [create_error_code(deep_exception) for _ in range(10)]
    return " | ".join(f"unexpected error [{code}] in handler" for code in codes)


def test_create_error_code(benchmark, deep_exception: BaseException):
    result = benchmark(create_error_code, deep_exception)
    assert result.startswith("OEC:")


def test_parse_error_codes_from_log(benchmark, log_message: str):
    result = benchmark(parse_error_codes, log_message)
    assert len(result) == 10


def test_parse_error_code_parts(benchmark, deep_exception: BaseException):
    error_code = create_error_code(deep_exception)
    fingerprint, _ = benchmark(parse_error_code_parts, error_code)
    assert fingerprint
