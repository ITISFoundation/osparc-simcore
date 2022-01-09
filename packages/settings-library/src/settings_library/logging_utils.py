import logging
from functools import cached_property
from typing import Any


class MixinLoggingSettings:
    @classmethod
    def validate_log_level(cls, value: Any) -> str:
        try:
            getattr(logging, value.upper())
        except AttributeError as err:
            raise ValueError(f"{value.upper()} is not a valid level") from err
        return value.upper()

    @cached_property
    def log_level(self) -> int:
        """Can be used in logging.setLogLevel()"""
        assert issubclass(self.__class__, MixinLoggingSettings)  # nosec
        assert hasattr(self, "LOG_LEVEL")  # nosec
        return getattr(logging, self.LOG_LEVEL.upper())  # type: ignore # pylint: disable=no-member
