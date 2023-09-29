""" Utils for substitutions in string templates

"""
import re
import sys
from collections import UserDict
from string import Template
from typing import Any, Final

OSPARC_IDENTIFIER_PREFIX: Final[str] = "OSPARC_VARIABLE_"


def upgrade_identifier(identifier: str) -> str:
    """
    Converts legacy or incompatible identifiers into official replacement identifier
    """
    identifier = re.sub(r"[${}%]", "", identifier)
    identifier = re.sub(r"[.-]", "_", identifier)
    identifier = identifier.upper()
    if not identifier.startswith(OSPARC_IDENTIFIER_PREFIX):
        assert OSPARC_IDENTIFIER_PREFIX.endswith("_")  # nosec
        identifier = OSPARC_IDENTIFIER_PREFIX + identifier
    return identifier


# NOTE: includes % or %%
_LEGACY_IDENTIFIER_RE_PATTERN = re.compile(r"%{1,2}([_a-z][_a-z0-9\.\-]*)%{1,2}")


def substitute_all_legacy_identifiers(text: str) -> str:
    """Substitutes all legacy identifiers found in the text by the new format expected in TemplateText

    For instance:  '%%this-identifier%%' will be substituted by '$OSPARC_VARIABLE_THIS_IDENTIFIER'
    """

    def _upgrade(match):
        legacy_id = match.group(1)
        legacy_id = upgrade_identifier(legacy_id)
        return f"${legacy_id}"

    return re.sub(_LEGACY_IDENTIFIER_RE_PATTERN, _upgrade, text)


class TextTemplate(Template):
    """Template strings support `$`-based substitutions, using the following rules:

    - `$$` is an escape; it is replaced with a single `$`.
    - `$identifier` names a substitution placeholder matching a mapping key of `"identifier"`.
        By default, `"identifier"` is restricted to any case-insensitive ASCII alphanumeric string
        (including underscores) that starts with an underscore or ASCII letter.
        The first non-identifier character after the `$` character terminates this placeholder specification.
    - `${identifier}` is equivalent to `$identifier`. It is required when valid identifier characters follow the
        placeholder but are not part of the placeholder, such as `"${noun}ification"`.

    SEE https://docs.python.org/3/library/string.html#template-strings
    """

    if sys.version_info < (3, 11):
        # Backports methods added in py 3.11
        # NOTE: Keep it compatible with multiple version

        def is_valid(self):
            for mo in self.pattern.finditer(self.template):
                if mo.group("invalid") is not None:
                    return False
                if (
                    mo.group("named") is None
                    and mo.group("braced") is None
                    and mo.group("escaped") is None
                ):
                    # If all the groups are None, there must be
                    # another group we're not expecting
                    msg = "Unrecognized named group in pattern"
                    raise ValueError(msg, self.pattern)
            return True

        def get_identifiers(self):
            ids = []
            for mo in self.pattern.finditer(self.template):
                named = mo.group("named") or mo.group("braced")
                if named is not None and named not in ids:
                    # add a named group only the first time it appears
                    ids.append(named)
                elif (
                    named is None
                    and mo.group("invalid") is None
                    and mo.group("escaped") is None
                ):
                    # If all the groups are None, there must be
                    # another group we're not expecting
                    msg = "Unrecognized named group in pattern"
                    raise ValueError(msg, self.pattern)
            return ids


class SubstitutionsDict(UserDict):
    """Map of keys to be substituded in Template"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # NOTE: Consider using a counter here. Could be useful to implement a replace first/once policy.
        self.used = set()  # used keys

    def __getitem__(self, key) -> Any:
        value = super().__getitem__(key)
        self.used.add(key)
        return value

    @property
    def unused(self):
        return {key for key in self if key not in self.used}
