import datetime
import logging
from collections.abc import Iterator
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
        result += f"{int(milliseconds*1000)}ms"

    sign = "-" if total_seconds < 0 else ""

    return f"{sign}{result.strip()}"


class DynamicIndentFormatter(logging.Formatter):
    indent_char: str = "\t"
    _indent_level: int = 0

    def __init__(self, fmt=None, datefmt=None, style="%"):
        dynamic_fmt = fmt or "%(asctime)s %(levelname)s %(message)s"
        assert "message" in dynamic_fmt
        super().__init__(dynamic_fmt, datefmt, style)

    def format(self, record) -> str:
        original_message = record.msg
        record.msg = f"{self.indent_char * self._indent_level}{original_message}"
        result = super().format(record)
        record.msg = original_message
        return result

    @classmethod
    def increase_indent(cls) -> None:
        cls._indent_level += 1

    @classmethod
    def decrease_indent(cls) -> None:
        cls._indent_level = max(0, cls._indent_level - 1)

    @classmethod
    def setup(cls, logger: logging.Logger) -> None:
        _formatter = DynamicIndentFormatter()
        _handler = logging.StreamHandler()
        _handler.setFormatter(_formatter)
        logger.addHandler(_handler)
        logger.setLevel(logging.INFO)


test_logger = logging.getLogger(__name__)
DynamicIndentFormatter.setup(test_logger)


@dataclass
class ContextMessages:
    starting: str
    done: str
    raised: str = field(default="")

    def __post_init__(self):
        if not self.raised:
            self.raised = f"{self.done} [with error]"


LogLevelInt: TypeAlias = int
LogMessageStr: TypeAlias = str


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
            starting=f"-> {msg} starting ...",
            done=f"<- {msg} done",
            raised=f"! {msg} raised",
        )
    elif isinstance(msg, tuple):
        ctx_msg = ContextMessages(*msg)
    else:
        ctx_msg = msg

    started_time = datetime.datetime.now(tz=datetime.timezone.utc)
    try:
        DynamicIndentFormatter.increase_indent()

        logger.log(level, ctx_msg.starting, *args, **kwargs)

        yield SimpleNamespace(logger=logger, messages=ctx_msg)
        elapsed_time = datetime.datetime.now(tz=datetime.timezone.utc) - started_time
        done_message = (
            f"{ctx_msg.done} ({_timedelta_as_minute_second_ms(elapsed_time)})"
        )
        logger.log(
            level,
            done_message,
            *args,
            **kwargs,
        )

    except:
        elapsed_time = datetime.datetime.now(tz=datetime.timezone.utc) - started_time
        error_message = (
            f"{ctx_msg.raised} ({_timedelta_as_minute_second_ms(elapsed_time)})"
        )
        logger.log(
            logging.ERROR,
            error_message,
            *args,
            **kwargs,
        )
        raise

    finally:
        DynamicIndentFormatter.decrease_indent()
