from typing import NamedTuple

import pytest
from models_library.basic_types import EnvVarKey, UUIDStr
from pydantic import ConstrainedStr, ValidationError
from pydantic.tools import parse_obj_as


class _Example(NamedTuple):
    constr: type[ConstrainedStr]
    good: str
    bad: str


_EXAMPLES = [
    _Example(constr=EnvVarKey, good="env_VAR", bad="12envar"),
    _Example(
        constr=UUIDStr,
        good="d2cbbd98-d0f8-4de1-864e-b390713194eb",
        bad="123456-is-not-an-uuid",
    ),
]


@pytest.mark.parametrize(
    "constraint_str_type,sample",
    [(p.constr, p.good) for p in _EXAMPLES],
)
def test_constrained_str_succeeds(
    constraint_str_type: type[ConstrainedStr], sample: str
):
    assert parse_obj_as(constraint_str_type, sample) == sample


@pytest.mark.parametrize(
    "constraint_str_type,sample",
    [(p.constr, p.bad) for p in _EXAMPLES],
)
def test_constrained_str_fails(constraint_str_type: type[ConstrainedStr], sample: str):
    with pytest.raises(ValidationError):
        parse_obj_as(constraint_str_type, sample)
