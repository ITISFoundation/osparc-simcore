# pylint: disable=broad-except
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging

import pytest
from common_library.error_codes import create_error_code, parse_error_code

logger = logging.getLogger(__name__)


def _level_three(v):
    msg = f"An error occurred in level three with {v}"
    raise RuntimeError(msg)


def _level_two(v):
    _level_three(v)


def _level_one(v=None):
    _level_two(v)


def test_exception_fingerprint_consistency():
    error_codes = []

    for v in range(2):
        # emulates different runs of the same function (e.g. different sessions)
        try:
            _level_one(v)  # same even if different value!
        except Exception as err:
            error_code = create_error_code(err)
            error_codes.append(error_code)

    assert error_codes == [error_codes[0]] * len(error_codes)

    try:
        # Same function but different location
        _level_one(0)
    except Exception as e2:
        error_code_2 = create_error_code(e2)
        assert error_code_2 != error_code[0]


def test_create_log_and_parse_error_code(caplog: pytest.LogCaptureFixture):
    with pytest.raises(RuntimeError) as exc_info:
        _level_one()

    # 1. Unexpected ERROR
    err = exc_info.value

    # 2. create error-code
    error_code = create_error_code(err)

    # 3. log all details in service
    caplog.clear()

    # Can add a formatter that prefix error-codes
    syslog = logging.StreamHandler()
    syslog.setFormatter(logging.Formatter("%(asctime)s %(error_code)s : %(message)s"))
    logger.addHandler(syslog)

    logger.exception("Fake Unexpected error", extra={"error_code": error_code})

    # logs something like E.g. 2022-07-06 14:31:13,432 OEC:140350117529856 : Fake Unexpected error
    assert parse_error_code(
        f"2022-07-06 14:31:13,432 {error_code} : Fake Unexpected error"
    ) == {
        error_code,
    }

    assert caplog.records[0].error_code == error_code
    assert caplog.records[0]

    logger.exception("Fake without error_code")

    # 4. inform user (e.g. with new error or sending message)
    user_message = (
        f"This is a user-friendly message to inform about an error. [{error_code}]"
    )

    assert parse_error_code(user_message) == {
        error_code,
    }
