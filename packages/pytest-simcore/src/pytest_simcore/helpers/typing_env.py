from collections.abc import Iterable
from typing import TypeAlias

EnvVarsDict: TypeAlias = dict[str, str]
type EnvVarsIterable = Iterable[str]


# SEE packages/pytest-simcore/tests/test_helpers_utils_envs.py
