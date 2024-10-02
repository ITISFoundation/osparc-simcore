""" Regular expressions patterns to build pydantic contrained strings

    - Variants of the patterns with 'Named Groups' captured are suffixed with NG_RE

    SEE tests_basic_regex.py for examples
"""
# TODO: for every pattern we should have a formatter function
# NOTE: some sites to manualy check ideas
#   https://regex101.com/
#   https://pythex.org/
#

# Universally unique Identifier. Pattern taken from https://stackoverflow.com/questions/136505/searching-for-uuids-in-text-with-regex
import re
from typing import Final

UUID_RE_BASE = (
    r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}"
)
UUID_RE = rf"^{UUID_RE_BASE}$"

# Formatted timestamps with date and time
DATE_RE = r"\d{4}-(12|11|10|0?[1-9])-(31|30|[0-2]?\d)T(2[0-3]|1\d|0?[0-9])(:(\d|[0-5]\d)){2}(\.\d{3})?Z"


# python-like version
SIMPLE_VERSION_RE = r"^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$"

# Semantic version
# SEE https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string
#
# with capture groups: cg1 = major, cg2 = minor, cg3 = patch, cg4 = prerelease and cg5 = buildmetadata
SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
# with named groups: major, minor, patch, prerelease and buildmetadata
SEMANTIC_VERSION_RE_W_NAMED_GROUPS = r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"


# Regex to detect whether a string can be used as a variable identifier (see tests)
#  - cannot start with spaces, _ (we only want public) or numbers
# https://docs.python.org/3/reference/lexical_analysis.html#identifiers
PUBLIC_VARIABLE_NAME_RE = r"^[^_\W0-9]\w*$"

MIME_TYPE_RE = (
    r"([\w\*]*)\/(([\w\-\*]+\.)+)?([\w\-\*]+)(\+([\w\-\.]+))?(; ([\w+-\.=]+))?"
)

# Storage basic file ID
SIMCORE_S3_FILE_ID_RE = rf"^(api|({UUID_RE_BASE}))\/({UUID_RE_BASE})\/(.+)$"
SIMCORE_S3_DIRECTORY_ID_RE = rf"^({UUID_RE_BASE})\/({UUID_RE_BASE})\/(.+)\/$"

# S3 - AWS bucket names [https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html]
S3_BUCKET_NAME_RE = re.compile(
    r"^(?!xn--)[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$(?<!-s3alias)"
)

# Datcore file ID
DATCORE_FILE_ID_RE = rf"^N:package:{UUID_RE_BASE}$"
DATCORE_DATASET_NAME_RE = rf"^N:dataset:{UUID_RE_BASE}$"


TWILIO_ALPHANUMERIC_SENDER_ID_RE = r"(?!^\d+$)^[a-zA-Z0-9\s]{2,11}$"
#   Alphanumeric Sender IDs may be up to 11 characters long.
#   Accepted characters include both upper- and lower-case Ascii letters,
#   the digits 0 through 9, and the space character.
#   They may not be only numerals.


# Docker
DOCKER_LABEL_KEY_REGEX: Final[re.Pattern] = re.compile(
    # NOTE: https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
    r"^(?!(\.|\-|com.docker\.|io.docker\.|org.dockerproject\.|\d))(?!.*(--|\.\.))[a-z0-9\.-]+(?<![\d\.\-])$"
)
DOCKER_GENERIC_TAG_KEY_RE: Final[re.Pattern] = re.compile(
    # NOTE: https://docs.docker.com/engine/reference/commandline/tag/#description
    r"^(?:(?P<registry_host>[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?|[a-z0-9-]+:\d+)/)?"
    r"(?P<docker_image>(?:[a-z0-9][a-z0-9_.-]*/)*[a-z0-9-_]+[a-z0-9])"
    r"(?::(?P<docker_tag>[\w][\w.-]{0,127}))?"
    r"(?P<docker_digest>\@sha256:[a-fA-F0-9]{32,64})?$"
)

PROPERTY_KEY_RE = r"^[-_a-zA-Z0-9]+$"  # TODO: PC->* it would be advisable to have this "variable friendly" (see VARIABLE_NAME_RE)
