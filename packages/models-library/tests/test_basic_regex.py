# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import keyword
import re
from collections.abc import Sequence
from datetime import datetime
from re import Pattern
from typing import Any

import pytest
from models_library.basic_regex import (
    DATE_RE,
    DOCKER_GENERIC_TAG_KEY_RE,
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
    regex_or_str: str | Pattern[str],
    test_str: str,
    expected: Any,
    *,
    group_names: tuple[str] | None = None,
) -> Sequence | None:
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


@pytest.mark.parametrize(
    "sample, expected",
    [
        ("fedora/httpd:version1.0", VALID),
        ("fedora/httpd:version1.0.test", VALID),
        ("itisfoundation/dynamic-sidecar:release-latest", VALID),
        ("simcore/service/comp/itis/sleepers:2.0.2", VALID),
        ("registry.osparc.io/simcore/service/comp/itis/sleepers:2.0.2", VALID),
        ("nginx:2.0.2", VALID),
        ("envoyproxy/envoy:v1.25-latest", VALID),
        ("myregistryhost:5000/fedora/httpd:version1.0", VALID),
        ("alpine", VALID),
        ("alpine:latest", VALID),
        ("localhost/latest", VALID),
        ("library/alpine", VALID),
        ("localhost:1234/test", VALID),
        ("test:1234/blaboon", VALID),
        ("alpine:3.7", VALID),
        ("docker.example.edu/gmr/alpine:3.7", VALID),
        (
            "docker.example.com:5000/gmr/alpine@sha256:5a156ff125e5a12ac7ff43ee5120fa249cf62248337b6d04abc574c8",
            VALID,
        ),
        ("docker.example.co.uk/gmr/alpine/test2:latest", VALID),
        ("registry.dobby.org/dobby/dobby-servers/arthound:2019-08-08", VALID),
        ("owasp/zap:3.8.0", VALID),
        ("registry.dobby.co/dobby/dobby-servers/github-run:2021-10-04", VALID),
        ("docker.elastic.co/kibana/kibana:7.6.2", VALID),
        ("registry.dobby.org/dobby/dobby-servers/lerphound:latest", VALID),
        ("registry.dobby.org/dobby/dobby-servers/marbletown-poc:2021-03-29", VALID),
        ("marbles/marbles:v0.38.1", VALID),
        (
            "registry.dobby.org/dobby/dobby-servers/loophole@sha256:5a156ff125e5a12ac7ff43ee5120fa249cf62248337b6d04abc574c8",
            VALID,
        ),
        ("sonatype/nexon:3.30.0", VALID),
        ("prom/node-exporter:v1.1.1", VALID),
        (
            "sosedoff/pgweb@sha256:5a156ff125e5a12ac7ff43ee5120fa249cf62248337b6d04abc574c8",
            VALID,
        ),
        ("sosedoff/pgweb:latest", VALID),
        ("registry.dobby.org/dobby/dobby-servers/arpeggio:2021-06-01", VALID),
        ("registry.dobby.org/dobby/antique-penguin:release-production", VALID),
        ("dalprodictus/halcon:6.7.5", VALID),
        ("antigua/antigua:v31", VALID),
        ("weblate/weblate:4.7.2-1", VALID),
        ("redis:4.0.01-alpine", VALID),
        ("registry.dobby.com/dobby/dobby-servers/github-run:latest", VALID),
        ("portainer/portainer:latest", VALID),
        (
            "registry:2@sha256:5a156ff125e5a12ac7fdec2b90b7e2ae5120fa249cf62248337b6d04abc574c8",
            VALID,
        ),
        ("alpine", VALID),
        ("alpine:latest", VALID),
        ("library/alpine", VALID),
        ("localhost/test", VALID),
        ("localhost:1234/test", VALID),
        ("test:1234/bla", VALID),
        ("alpine:3.7", VALID),
        ("docker.example.com/gmr/alpine:3.7", VALID),
        ("docker.example.com/gmr/alpine/test2:3.7", VALID),
        ("docker.example.com/gmr/alpine/test2/test3:3.7", VALID),
        ("docker.example.com:5000/gmr/alpine:latest", VALID),
        (
            "docker.example.com:5000/gmr/alpine:latest@sha256:5ae13221a775e9ded1d00f4dd6a3ad869ed1d662eb8cf81cb1fc2ba06f2b7172",
            VALID,
        ),
        (
            "docker.example.com:5000/gmr/alpine/test2:latest@sha256:5ae13221a775e9ded1d00f4dd6a3ad869ed1d662eb8cf81cb1fc2ba06f2b7172",
            VALID,
        ),
        (
            "docker.example.com/gmr/alpine/test2:latest@sha256:5ae13221a775e9ded1d00f4dd6a3ad869ed1d662eb8cf81cb1fc2ba06f2b7172",
            VALID,
        ),
        (
            "docker.example.com/gmr/alpine/test2@sha256:5ae13221a775e9ded1d00f4dd6a3ad869ed1d662eb8cf81cb1fc2ba06f2b7172",
            VALID,
        ),
        ("myregist_ryhost:5000/fedora/httpd:version1.0", INVALID),  # undescrore
        ("myregistryhost:5000/fe_dora/http_d:ver_sion1.0", VALID),
        ("myregistryHOST:5000/fedora/httpd:version1.0", INVALID),  # upper case
        ("myregistryhost:5000/fedora/httpd:-version1.0", INVALID),  # tag starts with -
        ("myregistryhost:5000/fedora/httpd:.version1.0", INVALID),  # tag starts with .
        (
            "simcore/services/dynamic/some/sub/folder/my_service-key:123.456.3214@sha256:2aef165ab4f30fbb109e88959271d8b57489790ea13a77d27c02d8adb8feb20f",
            VALID,
        ),
    ],
    ids=lambda d: f"{d if isinstance(d, str) else ('INVALID' if d is INVALID else 'VALID')}",
)
def test_DOCKER_GENERIC_TAG_KEY_RE(sample, expected):
    assert_match_and_get_capture(DOCKER_GENERIC_TAG_KEY_RE, sample, expected)
