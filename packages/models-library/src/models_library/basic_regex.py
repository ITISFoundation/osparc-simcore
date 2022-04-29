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

UUID_RE = r"\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b"

# Formatted timestamps with date and time
DATE_RE = r"\d{4}-(12|11|10|0?[1-9])-(31|30|[0-2]?\d)T(2[0-3]|1\d|0?[0-9])(:(\d|[0-5]\d)){2}(\.\d{3})?Z"


VERSION_RE = r"^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$"


# Regex to detect whether a string can be used as a variable identifier (see tests)
#  - cannot start with spaces, _ (we only want public) or numbers
# https://docs.python.org/3/reference/lexical_analysis.html#identifiers
PUBLIC_VARIABLE_NAME_RE = r"^[^_\W0-9]\w*$"

MIME_TYPE_RE = (
    r"([\w\*]*)\/(([\w\-\*]+\.)+)?([\w\-\*]+)(\+([\w\-\.]+))?(; ([\w+-\.=]+))?"
)
