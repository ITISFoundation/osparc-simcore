""" Utils for substitutions in string templates

"""
import re
from collections import UserDict
from string import Template
from typing import Any


def upgrade_identifier(legacy_id):
    legacy_id = re.sub(r"[{}%]", "", legacy_id)
    legacy_id = re.sub(r"[.-]", "_", legacy_id)
    legacy_id = legacy_id.upper()
    if not legacy_id.startswith("OSPARC_ENVIRONMENT_"):
        legacy_id = f"OSPARC_ENVIRONMENT_{legacy_id}"
    return legacy_id


LEGACY_FULL_IDENTIFIER_PATTERN = re.compile(r"%{1,2}([_a-z][_a-z0-9\.\-]*)%{1,2}")


def substitute_all_legacy_identifiers(text: str):
    def _upgrade(match):
        legacy_id = match.group(1)
        legacy_id = upgrade_identifier(legacy_id)
        return f"${legacy_id}"

    return re.sub(LEGACY_FULL_IDENTIFIER_PATTERN, _upgrade, text)


class TemplatePy311Mixin:
    # NOTE: Remove these two in py3.11
    # SEE https://github.com/python/cpython/blob/main/Lib/string.py#L144
    #

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
                raise ValueError("Unrecognized named group in pattern", self.pattern)
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
                raise ValueError("Unrecognized named group in pattern", self.pattern)
        return ids


class TemplateText(Template, TemplatePy311Mixin):
    # SEE https://docs.python.org/3/library/string.html#template-strings
    ...


class SubstitutionsDict(UserDict):
    """Map of keys to be substituded in Template"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.used = set()  # used keys

    def __getitem__(self, key) -> Any:
        value = super().__getitem__(key)
        self.used.add(key)
        return value

    @property
    def unused(self):
        return {key for key in self.keys() if key not in self.used}
