import logging
from functools import cached_property

from common_library.basic_types import LogLevel


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
    def log_level(self) -> int:
        """Can be used in logging.setLogLevel()"""
        assert issubclass(self.__class__, MixinLoggingSettings)  # nosec
        assert hasattr(self, "LOG_LEVEL")  # nosec
        return getattr(logging, self.LOG_LEVEL.upper())  # type: ignore # pylint: disable=no-member
