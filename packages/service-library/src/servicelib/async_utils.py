import asyncio
import logging
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from common_library.async_tools import cancel_wait_task

from . import tracing
from .logging_utils import log_catch

_logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


if TYPE_CHECKING:
    Queue = asyncio.Queue
else:

    class FakeGenericMeta(type):
        def __getitem__(self, item):
            return self

    class Queue(asyncio.Queue, metaclass=FakeGenericMeta):  # pylint: disable=function-redefined
        pass


@dataclass
class QueueElement:
    tracing_context: tracing.TracingContext
    input: Awaitable | None = None
    output: Any | None = None


@dataclass
class Context:
    _in_queue: asyncio.Queue[QueueElement]
    _out_queue: asyncio.Queue[Any]
    task: asyncio.Task | None = None
    _n_users: int = 0

    async def put(self, item: Any) -> None:
        await self._in_queue.put(item)

    async def get(self) -> Any:
        item = await self._out_queue.get()
        self._out_queue.task_done()
        return item


# NOTE: If you get issues with event loop already closed error use ensure_run_in_sequence_context_is_empty fixture in your tests
_sequential_jobs_contexts: dict[str, Context] = {}


def _generate_context_key(
    function: Callable[P, Awaitable[R]],
    target_args: list[str],
    args: Any,
    kwargs: dict,
) -> str:
    arg_names = function.__code__.co_varnames[: function.__code__.co_argcount]
    search_args = dict(zip(arg_names, args, strict=False))
    search_args.update(kwargs)

    key_parts: deque[str] = deque()
    for arg in target_args:
        sub_args = arg.split(".")
        main_arg = sub_args[0]
        if main_arg not in search_args:
            msg = f"Expected '{main_arg}' in '{function.__name__}' arguments. Got '{search_args}'"
            raise ValueError(msg)
        context_key = search_args[main_arg]
        for attribute in sub_args[1:]:
            potential_key = getattr(context_key, attribute)
            if not potential_key:
                msg = f"Expected '{attribute}' attribute in '{context_key.__name__}' arguments."
                raise ValueError(msg)
            context_key = potential_key

        key_parts.append(f"{function.__name__}_{context_key}")

    key = ":".join(map(str, key_parts))
    return key


@asynccontextmanager
async def _sequential_worker(
    context_key: str,
) -> AsyncIterator[Context]:
    key = context_key
    if key not in _sequential_jobs_contexts:
        _context = Context(
            _in_queue=asyncio.Queue(),
            _out_queue=asyncio.Queue(),
        )

        async def worker(in_q: Queue[QueueElement], out_q: Queue) -> None:
            while True:
                try:
                    element = await asyncio.wait_for(in_q.get(), timeout=1.0)
                    in_q.task_done()
                    with tracing.use_tracing_context(element.tracing_context):
                        try:
                            awaitable = element.input
                            if awaitable is None:
                                break
                            result = await awaitable
                        except Exception as e:  # pylint: disable=broad-except
                            result = e
                    await out_q.put(result)
                except TimeoutError:
                    continue

            logging.debug(
                "Closed worker for @run_sequentially_in_context applied to '%s'",
                key,
            )

        _context.task = asyncio.create_task(
            worker(
                _context._in_queue,  # pylint: disable=protected-access
                _context._out_queue,  # pylint: disable=protected-access
            )
        )
        _sequential_jobs_contexts[key] = _context

    context = _sequential_jobs_contexts[key]

    try:
        context._n_users += 1  # pylint: disable=protected-access
        yield context
    finally:
        # NOTE: Popping the context from _sequential_jobs_contexts must be done synchronously after it is checked that the context is not in use
        # to avoid new tasks being added to the context before it is removed.
        context._n_users -= 1  # pylint: disable=protected-access
        if context._n_users == 0:  # pylint: disable=protected-access
            if key in _sequential_jobs_contexts:
                context = _sequential_jobs_contexts.pop(key)
            if context.task is not None:
                with log_catch(_logger, reraise=False):
                    await cancel_wait_task(context.task, max_delay=None)


# NOTE: If you get funny mismatches with mypy in returned values it might be due to this decorator.
# @run_sequentially_in_contextreturn changes the return type of the decorated function to `Any`.
# Instead we should annotate this decorator with ParamSpec and TypeVar generics.
# SEE https://peps.python.org/pep-0612/
#
def run_sequentially_in_context(
    target_args: list[str] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """All request to function with same calling context will be run sequentially.

    Example:

    Given the following decorated function

        @run_sequentially_in_context(target_args=["param3", "param1"])
        async def func(param1, param2, param3):
            await asyncio.sleep(1)

    The context will be formed by the values of the arguments "param3" and "param1".
    The values must be serializable as they will be converted to string
    and put together as storage key for the context.

    The below calls will all run in a sequence:

        functions = [
            func(1, "something", 3),
            func(1, "argument.attribute", 3),
            func(1, "here", 3),
        ]
        await asyncio.gather(*functions)

    note the special "argument.attribute", which will use the attribute of argument to create the context.

    The following calls will run in parallel, because they have different contexts:

        functions = [
            func(1, "something", 3),
            func(2, "else", 3),
            func(3, "here", 3),
        ]
        await asyncio.gather(*functions)

    """
    target_args = [] if target_args is None else target_args

    def decorator(
        decorated_function: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        @wraps(decorated_function)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            async with _sequential_worker(
                _generate_context_key(
                    function=decorated_function,
                    target_args=target_args,
                    args=args,
                    kwargs=kwargs,
                )
            ) as context:
                queue_input = QueueElement(
                    input=decorated_function(*args, **kwargs),
                    tracing_context=tracing.get_context(),
                )
                await context.put(queue_input)
                wrapped_result = await context.get()

                if isinstance(wrapped_result, Exception):
                    raise wrapped_result
                result: R = wrapped_result
                return result

        return wrapper

    return decorator
