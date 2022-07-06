# pylint: disable=broad-except
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging

from servicelib.errors import create_error_code, parse_error_code

logger = logging.getLogger(__name__)


def test_error_code_use_case(caplog):
    """use case for error-codes"""
    try:
        raise RuntimeError("Something unexpected went wrong")
    except Exception as err:
        # 1. Unexpected ERROR

        # 2. create error-code
        error_code = create_error_code(err)

        # 3. log all details in service
        caplog.clear()

        # Can add a formatter that prefix error-codes
        syslog = logging.StreamHandler()
        syslog.setFormatter(
            logging.Formatter("%(asctime)s %(error_code)s : %(message)s")
        )
        logger.addHandler(syslog)

        logger.error("Fake Unexpected error", extra={"error_code": error_code})

        # logs something like E.g. 2022-07-06 14:31:13,432 OEC:140350117529856 : Fake Unexpected error
        assert parse_error_code(
            f"2022-07-06 14:31:13,432 {error_code} : Fake Unexpected error"
        ) == {
            error_code,
        }

        assert caplog.records[0].error_code == error_code
        assert caplog.records[0]

        logger.error("Fake without error_code")

        # 4. inform user (e.g. with new error or sending message)
        user_message = (
            f"This is a user-friendly message to inform about an error. [{error_code}]"
        )

        assert parse_error_code(user_message) == {
            error_code,
        }
