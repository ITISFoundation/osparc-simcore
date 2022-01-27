import keyword

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
import re
from datetime import datetime
from typing import Optional, Sequence

import pytest
from models_library.basic_regex import DATE_RE, UUID_RE, VARIABLE_NAME_RE, VERSION_RE
from packaging.version import Version

INVALID = object()
VALID = object()
NOT_CAPTURED = ()


def assert_match_and_get_capture(regex_str, test_str, expected) -> Optional[Sequence]:
    match = re.match(regex_str, test_str)
    if expected is INVALID:
        assert match is None
    elif expected is VALID:
        assert match is not None
        print(regex_str, "captured:", match.group(), "->", match.groups())
    else:
        captured = match.groups()
        assert captured == expected
        return captured
    return None


@pytest.mark.parametrize(
    "version_str, expected",
    [
        ("0.10.9", ("0", ".9", "9", None, None, None, None, None, None)),
        ("01.10.9", INVALID),
        ("2.1.0-rc2", ("2", ".0", "0", "-rc2", "rc2", None, None, None, None)),
    ],
)
def test_VERSION_RE(version_str, expected):
    assert_match_and_get_capture(VERSION_RE, version_str, expected)


@pytest.mark.parametrize(
    "uuid_str, expected",
    [
        ("55adf2b1-69fb-4a40-b21e-763585832ec1", NOT_CAPTURED),
        ("project-template-1233445", INVALID),
    ],
)
def test_UUID_RE(uuid_str, expected):
    assert_match_and_get_capture(UUID_RE, uuid_str, expected)


class webserver_timedate_utils:
    # TODO: move these utils here from webserver
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    @classmethod
    def now(cls) -> datetime:
        return datetime.utcnow()

    @classmethod
    def format_datetime(cls, snapshot: datetime) -> str:
        """Returns formatted time snapshot in UTC"""
        # FIXME: ensure snapshot is ZULU time!
        return "{}Z".format(snapshot.isoformat(timespec="milliseconds"))

    @classmethod
    def now_str(cls) -> str:
        return cls.format_datetime(cls.now())

    @classmethod
    def to_datetime(cls, snapshot: str) -> datetime:
        return datetime.strptime(snapshot, cls.DATETIME_FORMAT)


@pytest.mark.parametrize(
    "date_str, expected",
    [
        ("2020-12-30T23:15:00.345Z", ("12", "30", "23", ":00", "00", ".345")),
        ("2020-12-30 23:15:00", INVALID),
        (datetime.now().isoformat(), INVALID),  # as '2020-11-29T23:09:21.859469'
        (datetime.utcnow().isoformat(), INVALID),  # as '2020-11-29T22:09:21.859469'
        (webserver_timedate_utils.now_str(), VALID),
        (
            webserver_timedate_utils.format_datetime(
                datetime(2020, 11, 29, 22, 13, 23, 57000)
            ),
            ("11", "29", "22", ":23", "23", ".057"),
        ),  # '2020-11-29T22:13:23.057Z'
    ],
)
def test_DATE_RE(date_str, expected):
    assert_match_and_get_capture(DATE_RE, date_str, expected)


def test_pep404_compare_versions():
    # A reminder from https://setuptools.readthedocs.io/en/latest/userguide/distribution.html#specifying-your-project-s-version
    assert Version("1.9.a.dev") == Version("1.9a0dev")
    assert Version("2.1-rc2") < Version("2.1")
    assert Version("0.6a9dev") < Version("0.6a9")


@pytest.mark.parametrize(
    "string_under_test",
    (
        "x1",
        "a_very_long_variable_22",
        "a-string-with-minus",
        "1xxx",
        "str w/ spaces",
        "a./b.c",
        "def",
        "for",
        "in",
    ),
)
def test_variable_names_regex(string_under_test):
    variable_re = re.compile(VARIABLE_NAME_RE)

    if string_under_test.isidentifier():
        # This is what we could do in case it is a keyword (added as validator( ... pre=True) )
        # SEE https://docs.python.org/3/library/stdtypes.html?highlight=isidentifier#str.isidentifier
        if keyword.iskeyword(string_under_test):
            string_under_test += "_"

        assert variable_re.match(string_under_test)
    else:
        assert not variable_re.match(string_under_test)
