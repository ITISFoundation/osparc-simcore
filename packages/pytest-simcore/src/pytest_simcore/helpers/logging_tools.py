import datetime
import logging
import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Final, TypeAlias


def _timedelta_as_minute_second_ms(delta: datetime.timedelta) -> str:
    total_seconds = delta.total_seconds()
    minutes, rem_seconds = divmod(abs(total_seconds), 60)
    seconds, milliseconds = divmod(rem_seconds, 1)
    result = ""

    if int(minutes) != 0:
        result += f"{int(minutes)}m "

    if int(seconds) != 0:
        result += f"{int(seconds)}s "

    if int(milliseconds * 1000) != 0:
        result += f"{int(milliseconds * 1000)}ms"
    if not result:
        result = "<1ms"

    sign = "-" if total_seconds < 0 else ""

    return f"{sign}{result.strip()}"


def _resolve(val: str | Callable[[], str], prefix: str, suffix: str) -> str:
    try:
        return f"{prefix}{val if isinstance(val, str) else val()}{suffix}"
    except Exception as exc:  # pylint: disable=broad-exception-caught
        warnings.warn(
            f"Failed to generate {val} message: {exc!r}. "
            f"Fix the callable to return a string without raising exceptions.",
            UserWarning,
            stacklevel=3,
        )
        return f"❌❌❌ [{val} message generation failed TIP: Check how the {val} message is generated!] ❌❌❌"


class DynamicIndentFormatter(logging.Formatter):
    indent_char: str = "    "
    _cls_indent_level: int = 0
    _instance_indent_level: int = 0

    def __init__(self, *args, **kwargs):
        fmt = args[0] if args else None
        dynamic_fmt = fmt or "%(asctime)s %(levelname)s %(message)s"
        assert "message" in dynamic_fmt
        super().__init__(dynamic_fmt, *args, **kwargs)

    def format(self, record) -> str:
        original_message = record.msg
        record.msg = f"{self.indent_char * self._cls_indent_level}{self.indent_char * self._instance_indent_level}{original_message}"
        result = super().format(record)
        record.msg = original_message
        return result

    @classmethod
    def cls_increase_indent(cls) -> None:
        cls._cls_indent_level += 1

    @classmethod
    def cls_decrease_indent(cls) -> None:
        cls._cls_indent_level = max(0, cls._cls_indent_level - 1)

    def increase_indent(self) -> None:
        self._instance_indent_level += 1

    def decrease_indent(self) -> None:
        self._instance_indent_level = max(0, self._instance_indent_level - 1)

    @classmethod
    def setup(cls, logger: logging.Logger) -> None:
        _formatter = DynamicIndentFormatter()
        _handler = logging.StreamHandler()
        _handler.setFormatter(_formatter)
        logger.addHandler(_handler)


test_logger = logging.getLogger(__name__)
DynamicIndentFormatter.setup(test_logger)


# Message formatting constants
_STARTING_PREFIX: Final[str] = "--> "
_STARTING_SUFFIX: Final[str] = " ⏳"
_DONE_PREFIX: Final[str] = "<-- "
_DONE_SUFFIX: Final[str] = " ✅"
_RAISED_PREFIX: Final[str] = "❌❌❌ Error: "
_RAISED_SUFFIX: Final[str] = " ❌❌❌"
_STACK_LEVEL_OFFSET: Final[int] = 3


@dataclass
class ContextMessages:
    starting: str | Callable[[], str]
    done: str | Callable[[], str]
    raised: str | Callable[[], str] = field(default="")

    def __post_init__(self):
        if not self.raised:
            self.raised = (
                lambda: f"{self.done if isinstance(self.done, str) else self.done()} [with raised error]"
            )


LogLevelInt: TypeAlias = int
LogMessageStr: TypeAlias = str


@contextmanager
def _increased_logger_indent(logger: logging.Logger) -> Iterator[None]:
    try:
        if formatter := next(
            (
                h.formatter
                for h in logger.handlers
                if isinstance(h.formatter, DynamicIndentFormatter)
            ),
            None,
        ):
            formatter.increase_indent()
        yield
    finally:
        if formatter := next(
            (
                h.formatter
                for h in logger.handlers
                if isinstance(h.formatter, DynamicIndentFormatter)
            ),
            None,
        ):
            formatter.decrease_indent()


@contextmanager
def log_context(
    level: LogLevelInt,
    msg: LogMessageStr | tuple | ContextMessages,
    *args,
    logger: logging.Logger = test_logger,
    **kwargs,
) -> Iterator[SimpleNamespace]:
    # NOTE: Preserves original signature of a logger https://docs.python.org/3/library/logging.html#logging.Logger.log
    # NOTE: To add more info to the logs e.g. times, user_id etc prefer using formatting instead of adding more here

    if isinstance(msg, str):
        ctx_msg = ContextMessages(
            starting=f"{msg}",
            done=f"{msg}",
            raised=f"{msg}",
        )
    elif isinstance(msg, tuple):
        ctx_msg = ContextMessages(*msg)
    else:
        ctx_msg = msg

    started_time = datetime.datetime.now(tz=datetime.UTC)
    try:
        DynamicIndentFormatter.cls_increase_indent()

        logger.log(
            level,
            _resolve(ctx_msg.starting, _STARTING_PREFIX, _STARTING_SUFFIX),
            *args,
            **kwargs,
            stacklevel=_STACK_LEVEL_OFFSET,
        )
        with _increased_logger_indent(logger):
            yield SimpleNamespace(logger=logger, messages=ctx_msg)
        elapsed_time = datetime.datetime.now(tz=datetime.UTC) - started_time
        done_message = f"{_resolve(ctx_msg.done, _DONE_PREFIX, _DONE_SUFFIX)} (total time spent: {_timedelta_as_minute_second_ms(elapsed_time)})"
        logger.log(
            level,
            done_message,
            *args,
            **kwargs,
            stacklevel=_STACK_LEVEL_OFFSET,
        )

    except:
        elapsed_time = datetime.datetime.now(tz=datetime.UTC) - started_time
        error_message = f"{_resolve(ctx_msg.raised, _RAISED_PREFIX, _RAISED_SUFFIX)} (total time spent: {_timedelta_as_minute_second_ms(elapsed_time)})"
        logger.exception(
            error_message,
            *args,
            **kwargs,
            stacklevel=_STACK_LEVEL_OFFSET,
        )
        raise

    finally:
        DynamicIndentFormatter.cls_decrease_indent()
