# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import keyword
import re
from datetime import datetime, timezone
from typing import Any, Optional, Pattern, Sequence, Union

import pytest
from models_library.basic_regex import (
    DATE_RE,
    DOCKER_LABEL_KEY_REGEX,
    PUBLIC_VARIABLE_NAME_RE,
    SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS,
    SEMANTIC_VERSION_RE_W_NAMED_GROUPS,
    TWILIO_ALPHANUMERIC_SENDER_ID_RE,
    UUID_RE,
    VERSION_RE,
)
from packaging.version import Version

INVALID = object()
VALID = object()
NOT_CAPTURED = ()


def assert_match_and_get_capture(
    regex_or_str: Union[str, Pattern[str]],
    test_str: str,
    expected: Any,
    *,
    group_names: Optional[tuple[str]] = None,
) -> Optional[Sequence]:
    match = re.match(regex_or_str, test_str)
    if expected is INVALID:
        assert match is None
    elif expected is VALID:
        assert match is not None
        print(regex_or_str, "captured:", match.group(), "->", match.groups())
    else:
        assert match
        captured = match.groups()
        assert captured == expected

        if group_names:
            assert match.groupdict() == dict(zip(group_names, expected))
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


# Many taken from https://regex101.com/r/Ly7O1x/3/
VERSION_TESTFIXTURES = [
    ("0.0.4", ("0", "0", "4", None, None)),
    ("1.2.3", ("1", "2", "3", None, None)),
    ("10.20.30", ("10", "20", "30", None, None)),
    ("1.1.2-prerelease+meta", ("1", "1", "2", "prerelease", "meta")),
    ("1.1.2+meta", ("1", "1", "2", None, "meta")),
    ("1.1.2+meta-valid", ("1", "1", "2", None, "meta-valid")),
    ("1.0.0-alpha", ("1", "0", "0", "alpha", None)),
    ("1.0.0-beta", ("1", "0", "0", "beta", None)),
    ("1.0.0-alpha.beta", ("1", "0", "0", "alpha.beta", None)),
    ("1.0.0-alpha.beta.1", ("1", "0", "0", "alpha.beta.1", None)),
    ("1.0.0-alpha.1", ("1", "0", "0", "alpha.1", None)),
    ("1.0.0-alpha0.valid", ("1", "0", "0", "alpha0.valid", None)),
    ("1.0.0-alpha.0valid", ("1", "0", "0", "alpha.0valid", None)),
    (
        "1.0.0-alpha-a.b-c-somethinglong+build.1-aef.1-its-okay",
        ("1", "0", "0", "alpha-a.b-c-somethinglong", "build.1-aef.1-its-okay"),
    ),
    ("1.0.0-rc.1+build.1", ("1", "0", "0", "rc.1", "build.1")),
    ("2.0.0-rc.1+build.123", ("2", "0", "0", "rc.1", "build.123")),
    (
        "1.2.3----RC-SNAPSHOT.12.9.1--.12+788",
        ("1", "2", "3", "---RC-SNAPSHOT.12.9.1--.12", "788"),
    ),
    (
        "1.0.0+0.build.1-rc.10000aaa-kk-0.1",
        ("1", "0", "0", None, "0.build.1-rc.10000aaa-kk-0.1"),
    ),
    ("1.2", INVALID),
    ("1.2.3-0123", INVALID),
    ("1.2.3-0123.0123", INVALID),
    ("1.1.2+.123", INVALID),
    ("+invalid", INVALID),
    ("-invalid", INVALID),
    ("-invalid+invalid", INVALID),
    ("-invalid.01", INVALID),
    ("alpha", INVALID),
    ("alpha.beta", INVALID),
    ("alpha.beta.1", INVALID),
    ("alpha.1", INVALID),
    ("alpha+beta", INVALID),
    ("alpha_beta", INVALID),
    ("alpha.", INVALID),
    ("alpha..", INVALID),
    ("beta", INVALID),
    ("1.0.0-alpha_beta", INVALID),
    ("-alpha.", INVALID),
    ("1.0.0-alpha..", INVALID),
    ("1.0.0-alpha..1", INVALID),
    ("1.0.0-alpha...1", INVALID),
    ("1.0.0-alpha....1", INVALID),
    ("1.0.0-alpha.....1", INVALID),
    ("1.0.0-alpha......1", INVALID),
    ("1.0.0-alpha.......1", INVALID),
    ("01.1.1", INVALID),
    ("1.01.1", INVALID),
    ("1.1.01", INVALID),
    ("1.2", INVALID),
    ("1.2.3.DEV", INVALID),
    ("1.2-SNAPSHOT", INVALID),
    ("1.2.31.2.3----RC-SNAPSHOT.12.09.1--..12+788", INVALID),
    ("1.2-RC-SNAPSHOT", INVALID),
    ("-1.0.3-gamma+b7718", INVALID),
    ("+justmeta", INVALID),
    ("9.8.7+meta+meta", INVALID),
    ("9.8.7-whatever+meta+meta", INVALID),
    (
        "99999999999999999999999.999999999999999999.99999999999999999----RC-SNAPSHOT.12.09.1--------------------------------..12",
        INVALID,
    ),
]


@pytest.mark.parametrize("version_str, expected", VERSION_TESTFIXTURES)
def test_SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS(version_str: str, expected):
    # cg1 = major, cg2 = minor, cg3 = patch, cg4 = prerelease and cg5 = buildmetadata
    assert_match_and_get_capture(
        SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS, version_str, expected
    )


@pytest.mark.parametrize("version_str, expected", VERSION_TESTFIXTURES)
def test_SEMANTIC_VERSION_RE_W_NAMED_GROUPS(version_str: str, expected):
    assert_match_and_get_capture(
        SEMANTIC_VERSION_RE_W_NAMED_GROUPS,
        version_str,
        expected,
        group_names=("major", "minor", "patch", "prerelease", "buildmetadata"),
    )


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
        return datetime.now(timezone.utc).replace(tzinfo=None)

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
        (
            datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            INVALID,
        ),  # as '2020-11-29T22:09:21.859469'
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
    "string_under_test,expected_match",
    [
        ("a", True),
        ("x1", True),
        ("a_very_long_variable_22", True),
        ("a-string-with-minus", False),
        ("str w/ spaces", False),
        ("a./b.c", False),
        (".foo", False),
        ("1", False),
        ("1xxx", False),
        ("1-number-should-fail", False),
        ("-dash-should-fail", False),
        ("", False),
        # keywords
        ("def", False),
        ("for", False),
        ("in", False),
        # private/protected
        ("_", False),
        ("_protected", False),
    ],
)
def test_variable_names_regex(string_under_test, expected_match):
    variable_re = re.compile(PUBLIC_VARIABLE_NAME_RE)

    # NOTE: for keywords it is more difficult ot catch them in a regix.
    # Instead is better to add a validator( ... pre=True) in the field
    # that does the following check and invalidates them:
    # SEE https://docs.python.org/3/library/stdtypes.html?highlight=isidentifier#str.isidentifier
    if keyword.iskeyword(string_under_test):
        string_under_test = f"_{string_under_test}"

    if expected_match:
        assert variable_re.match(string_under_test)
    else:
        assert not variable_re.match(string_under_test)


@pytest.mark.parametrize(
    "sample, expected",
    [
        ("0123456789a", VALID),
        ("A12b4567 9a", VALID),
        ("01234567890", INVALID),  #  they may NOT be only numerals.
        ("0123456789a1", INVALID),  # may be up to 11 characters long
        ("0-23456789a", INVALID),  # '-' is invalid
    ],
)
def test_TWILIO_ALPHANUMERIC_SENDER_ID_RE(sample, expected):
    #   Alphanumeric Sender IDs may be up to 11 characters long.
    #   Accepted characters include both upper- and lower-case Ascii letters,
    #   the digits 0 through 9, and the space character.

    assert_match_and_get_capture(TWILIO_ALPHANUMERIC_SENDER_ID_RE, sample, expected)


@pytest.mark.parametrize(
    "sample, expected",
    [
        ("com.docker.*", INVALID),  # reserved
        ("io.docker.*", INVALID),  # reserved
        ("org.dockerproject.*", INVALID),  # reserved
        ("com.example.some-label", VALID),  # valid
        (
            "0sadfjh.sadf-dskhj",
            INVALID,
        ),  # starts with digit
        (
            "sadfjh.sadf-dskhj",
            VALID,
        ),  # only allow lowercasealphanumeric, being and end with letter, no consecutive -, .
        (
            "sadfjh.sadf-dskhj0",
            INVALID,
        ),  # ends with digit
        (
            "sadfjh.sadf-ds0khj",
            VALID,
        ),  # only allow lowercasealphanumeric, being and end with letter, no consecutive -, .
        (
            "sadfjh.EAGsadf-ds0khj",
            INVALID,
        ),  # upper case
        (
            "sadfjh..sadf-ds0khj",
            INVALID,
        ),  # double dot
        (
            "sadfjh.sadf--ds0khj",
            INVALID,
        ),  # double dash
        (
            "io.simcore.some234.cool.label",
            VALID,
        ),  # only allow lowercasealphanumeric, being and end with letter, no consecutive -, .
        (
            ".io.simcore.some234.cool",
            INVALID,
        ),  # starts with dot
        (
            "io.simcore.some234.cool.",
            INVALID,
        ),  # ends with dot
        (
            "-io.simcore.some234.cool",
            INVALID,
        ),  # starts with dash
        (
            "io.simcore.some234.cool-",
            INVALID,
        ),  # ends with dash
        (
            "io.simcore.so_me234.cool",
            INVALID,
        ),  # contains invalid character
    ],
    ids=lambda d: f"{d if isinstance(d, str) else ('INVALID' if d is INVALID else 'VALID')}",
)
def test_DOCKER_LABEL_KEY_REGEX(sample, expected):
    assert_match_and_get_capture(DOCKER_LABEL_KEY_REGEX, sample, expected)
