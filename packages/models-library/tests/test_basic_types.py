from typing import NamedTuple

import pytest
from models_library.basic_types import (
    EnvVarKey,
    IDStr,
    MD5Str,
    SHA1Str,
    ShortTruncatedStr,
    UUIDStr,
    VersionTag,
)
from pydantic import TypeAdapter, ValidationError


class _Example(NamedTuple):
    constr: type[str]
    good: str
    bad: str


_EXAMPLES = [
    _Example(constr=VersionTag, good="v5", bad="v5.2"),
    _Example(
        constr=SHA1Str,
        good="74e56e8a00c1ac4797eb15ada9affea692d48b25",
        bad="d2cbbd98-d0f8-4de1-864e-b390713194eb",
    ),  # sha1sum .pylintrc
    _Example(
        constr=MD5Str,
        good="3461a73124b5e63a1a0d912bc239cc94",
        bad="d2cbbd98-d0f8-4de1-864e-b390713194eb",
    ),  # md5sum .pylintrc
    _Example(constr=EnvVarKey, good="env_VAR", bad="12envar"),
    _Example(
        constr=UUIDStr,
        good="d2cbbd98-d0f8-4de1-864e-b390713194eb",
        bad="123456-is-not-an-uuid",
    ),
    _Example(
        constr=IDStr,
        good="d2cbbd98-d0f8-4de1-864e-b390713194eb",  # as an uuid
        bad="",  # empty string not allowed
    ),
]


@pytest.mark.parametrize(
    "constraint_str_type,sample",
    [(p.constr, p.good) for p in _EXAMPLES],
)
def test_constrained_str_succeeds(constraint_str_type: type[str], sample: str):
    assert TypeAdapter(constraint_str_type).validate_python(sample) == sample


@pytest.mark.parametrize(
    "constraint_str_type,sample",
    [(p.constr, p.bad) for p in _EXAMPLES],
)
def test_constrained_str_fails(constraint_str_type: type[str], sample: str):
    with pytest.raises(ValidationError):
        TypeAdapter(constraint_str_type).validate_python(sample)


def test_string_identifier_constraint_type():

    # strip spaces
    assert (
        TypeAdapter(IDStr).validate_python("   123 trim spaces   ") == "123 trim spaces"
    )

    # limited to 100!
    TypeAdapter(IDStr).validate_python("X" * IDStr.max_length)
    with pytest.raises(ValidationError):
        TypeAdapter(IDStr).validate_python("X" * (IDStr.max_length + 1))


def test_short_truncated_string():
    assert (
        TypeAdapter(ShortTruncatedStr).validate_python(
            "X" * ShortTruncatedStr.curtail_length
        )
        == "X" * ShortTruncatedStr.curtail_length
    )

    assert (
        TypeAdapter(ShortTruncatedStr).validate_python(
            "X" * (ShortTruncatedStr.curtail_length + 1)
        )
        == "X" * ShortTruncatedStr.curtail_length
    )
