from collections.abc import Iterable
from typing import TypeAlias

from frozendict import frozendict

EnvVarsDict: TypeAlias = dict[str, str]
FrozenEnvVarsDict: TypeAlias = frozendict[str, str]
EnvVarsIterable: TypeAlias = Iterable[str]


# SEE packages/pytest-simcore/tests/test_helpers_utils_envs.py
