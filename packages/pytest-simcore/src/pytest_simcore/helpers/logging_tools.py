import datetime
import logging
import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TypeAlias


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


def _resolve(val: str | Callable[[], str], context: str) -> str:
    """Resolve a message value that can be either a string or a callable.

    Args:
        val: The value to resolve (string or callable returning string)
        context: Description of which message this is for error reporting

    Returns:
        The resolved string value
    """
    if isinstance(val, str):
        return val
    try:
        return val()
    except Exception as exc:
        warnings.warn(
            f"Failed to generate {context} message: {exc!r}. "
            f"Fix the callable to return a string without raising exceptions.",
            UserWarning,
            stacklevel=3,
        )
        return f"[{context} message generation failed]"


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
        logger.setLevel(logging.INFO)


test_logger = logging.getLogger(__name__)
DynamicIndentFormatter.setup(test_logger)


# Message formatting constants
_STARTING_PREFIX = "--> "
_STARTING_SUFFIX = " ⏳"
_DONE_PREFIX = "<-- "
_DONE_SUFFIX = " ✅"
_RAISED_PREFIX = "❌❌❌ Error "
_RAISED_SUFFIX = " ❌❌❌"


@dataclass
class ContextMessages:
    starting: str | Callable[[], str]
    done: str | Callable[[], str]
    raised: str | Callable[[], str] = field(default="")

    def __post_init__(self):
        # Apply formatting to starting message
        if isinstance(self.starting, str):
            self.starting = f"{_STARTING_PREFIX}{self.starting}{_STARTING_SUFFIX}"
        else:
            original_starting = self.starting
            self.starting = (
                lambda: f"{_STARTING_PREFIX}{_resolve(original_starting, 'starting')}{_STARTING_SUFFIX}"
            )

        # Apply formatting to done message
        if isinstance(self.done, str):
            self.done = f"{_DONE_PREFIX}{self.done}{_DONE_SUFFIX}"
        else:
            original_done = self.done
            self.done = (
                lambda: f"{_DONE_PREFIX}{_resolve(original_done, 'done')}{_DONE_SUFFIX}"
            )

        # Apply formatting to raised message or create default
        if not self.raised:
            if isinstance(self.done, str):
                # Extract base message from formatted done message
                base_msg = self.done.replace(_DONE_PREFIX, "").replace(_DONE_SUFFIX, "")
                self.raised = f"{_RAISED_PREFIX}{base_msg}{_RAISED_SUFFIX}"
            else:
                original_done = self.done
                self.raised = (
                    lambda: f"{_RAISED_PREFIX}{_resolve(original_done, 'done')}{_RAISED_SUFFIX}"
                )
        elif isinstance(self.raised, str):
            self.raised = f"{_RAISED_PREFIX}{self.raised}{_RAISED_SUFFIX}"
        else:
            original_raised = self.raised
            self.raised = (
                lambda: f"{_RAISED_PREFIX}{_resolve(original_raised, 'raised')}{_RAISED_SUFFIX}"
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

        logger.log(level, _resolve(ctx_msg.starting, "starting"), *args, **kwargs)
        with _increased_logger_indent(logger):
            yield SimpleNamespace(logger=logger, messages=ctx_msg)
        elapsed_time = datetime.datetime.now(tz=datetime.UTC) - started_time
        done_message = f"{_resolve(ctx_msg.done, 'done')} ({_timedelta_as_minute_second_ms(elapsed_time)})"
        logger.log(
            level,
            done_message,
            *args,
            **kwargs,
        )

    except:
        elapsed_time = datetime.datetime.now(tz=datetime.UTC) - started_time
        error_message = f"{_resolve(ctx_msg.raised, 'raised')} ({_timedelta_as_minute_second_ms(elapsed_time)})"
        logger.exception(
            error_message,
            *args,
            **kwargs,
        )
        raise

    finally:
        DynamicIndentFormatter.cls_decrease_indent()
