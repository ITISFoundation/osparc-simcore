import logging
from functools import cached_property
from typing import Protocol

from common_library.basic_types import LogLevel


class _HasLogLevel(Protocol):
    LOG_LEVEL: str


class MixinLoggingSettings:
    """
    USAGE example in packages/settings-library/tests/test_utils_logging.py::test_mixin_logging
    """

    @classmethod
    def validate_log_level(cls, value: str) -> LogLevel:
        """Standard implementation for @validator("LOG_LEVEL")"""
        try:
            getattr(logging, value.upper())
        except AttributeError as err:
            msg = f"{value.upper()} is not a valid level"
            raise ValueError(msg) from err
        return LogLevel(value.upper())

    @cached_property
    def logging_level(self: _HasLogLevel) -> int:
        """Can be used in logging.setLogLevel()"""
        return logging.getLevelNamesMapping()[self.LOG_LEVEL.upper()]
