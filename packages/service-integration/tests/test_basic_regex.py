# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re

from service_integration import __version__
from service_integration.basic_regex import (
    PEP404_VERSION_RE,
    PEP440_VERSION_NG_RE,
    SEMANTIC_VERSION_NG_RE,
)


def test_semantic_version_with_named_groups():
    assert re.match(
        SEMANTIC_VERSION_NG_RE, "1.3.4-alpha.1+exp.sha.5114f85"
    ).groupdict() == {
        "major": "1",
        "minor": "3",
        "patch": "4",
        "prerelease": "alpha.1",
        "buildmetadata": "exp.sha.5114f85",
    }


def test_pep404_version():
    # Patterns from https://www.python.org/dev/peps/pep-0440/#appendix-b-parsing-version-strings-with-regular-expressions

    # see https://www.python.org/dev/peps/pep-0440/#examples-of-compliant-version-schemes

    assert re.match(PEP404_VERSION_RE, "1.0.dev456").groups() == (
        None,
        "1",
        ".0",
        "0",
        None,
        None,
        None,
        None,
        None,
        ".dev456",
        "456",
    )


def test_pep404_version_with_named_groups():
    # WARNING: not the options in re!!
    assert re.match(
        PEP440_VERSION_NG_RE,
        "1.0.dev456",
        re.VERBOSE | re.IGNORECASE,
    ).groupdict() == {
        "epoch": None,
        # release segment
        "release": "1.0",
        # pre-release
        "pre": None,
        "pre_l": None,
        "pre_n": None,
        # post-release
        "post": None,
        "post_l": None,
        "post_n1": None,
        "post_n2": None,
        # dev release
        "dev": ".dev456",
        "dev_l": "dev",
        "dev_n": "456",
        # local version
        "local": None,
    }
