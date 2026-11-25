from collections.abc import Iterable
from types import MappingProxyType
from typing import TypeAlias

EnvVarsDict: TypeAlias = dict[str, str]
FrozenEnvVarsDict: TypeAlias = MappingProxyType[str, str]
EnvVarsIterable: TypeAlias = Iterable[str]


# SEE packages/pytest-simcore/tests/test_helpers_utils_envs.py
