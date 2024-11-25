import asyncio
import logging
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Deque

from .utils_profiling_middleware import dont_profile, is_profiling, profile_context

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    Queue = asyncio.Queue
else:

    class FakeGenericMeta(type):
        def __getitem__(self, item):
            return self

    class Queue(
        asyncio.Queue, metaclass=FakeGenericMeta
    ):  # pylint: disable=function-redefined
        pass


@dataclass
class Context:
    in_queue: asyncio.Queue
    out_queue: asyncio.Queue
    initialized: bool
    task: asyncio.Task | None = None


@dataclass
class QueueElement:
    do_profile: bool = False
    input: Awaitable | None = None
    output: Any | None = None


# NOTE: If you get issues with event loop already closed error use ensure_run_in_sequence_context_is_empty fixture in your tests
_sequential_jobs_contexts: dict[str, Context] = {}


async def _safe_cancel(context: Context) -> None:
    try:
        await context.in_queue.put(None)
        if context.task is not None:
            context.task.cancel()
            with suppress(asyncio.CancelledError):
                await context.task
    except RuntimeError as e:
        if "Event loop is closed" in f"{e}":
            logger.warning("event loop is closed and could not cancel %s", context)
        else:
            raise


async def cancel_sequential_workers() -> None:
    """Signals all workers to close thus avoiding errors on shutdown"""
    for context in _sequential_jobs_contexts.values():
        await _safe_cancel(context)

    _sequential_jobs_contexts.clear()
    logger.info("All run_sequentially_in_context pending workers stopped")


# NOTE: If you get funny mismatches with mypy in returned values it might be due to this decorator.
# @run_sequentially_in_contextreturn changes the return type of the decorated function to `Any`.
# Instead we should annotate this decorator with ParamSpec and TypeVar generics.
# SEE https://peps.python.org/pep-0612/
#
def run_sequentially_in_context(
    target_args: list[str] | None = None,
) -> Callable:
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

    def decorator(decorated_function: Callable[[Any], Any | None]):
        def _get_context(args: Any, kwargs: dict) -> Context:
            arg_names = decorated_function.__code__.co_varnames[
                : decorated_function.__code__.co_argcount
            ]
            search_args = dict(zip(arg_names, args))
            search_args.update(kwargs)

            key_parts: Deque[str] = deque()
            for arg in target_args:
                sub_args = arg.split(".")
                main_arg = sub_args[0]
                if main_arg not in search_args:
                    raise ValueError(
                        f"Expected '{main_arg}' in '{decorated_function.__name__}'"
                        f" arguments. Got '{search_args}'"
                    )
                context_key = search_args[main_arg]
                for attribute in sub_args[1:]:
                    potential_key = getattr(context_key, attribute)
                    if not potential_key:
                        raise ValueError(
                            f"Expected '{attribute}' attribute in '{context_key.__name__}' arguments."
                        )
                    context_key = potential_key

                key_parts.append(f"{decorated_function.__name__}_{context_key}")

            key = ":".join(map(str, key_parts))

            if key not in _sequential_jobs_contexts:
                _sequential_jobs_contexts[key] = Context(
                    in_queue=asyncio.Queue(),
                    out_queue=asyncio.Queue(),
                    initialized=False,
                )

            return _sequential_jobs_contexts[key]

        # --------------------
        @wraps(decorated_function)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            context: Context = _get_context(args, kwargs)

            if not context.initialized:
                context.initialized = True

                async def worker(in_q: Queue[QueueElement], out_q: Queue) -> None:
                    while True:
                        element = await in_q.get()
                        in_q.task_done()
                        # check if requested to shutdown
                        try:
                            do_profile = element.do_profile
                            awaitable = element.input
                            if awaitable is None:
                                break
                            with profile_context(do_profile):
                                result = await awaitable
                        except Exception as e:  # pylint: disable=broad-except
                            result = e
                        await out_q.put(result)

                    logging.info(
                        "Closed worker for @run_sequentially_in_context applied to '%s' with target_args=%s",
                        decorated_function.__name__,
                        target_args,
                    )

                context.task = asyncio.create_task(
                    worker(context.in_queue, context.out_queue)
                )

            with dont_profile():
                # ensure profiler is disabled in order to capture profile of endpoint code
                queue_input = QueueElement(
                    input=decorated_function(*args, **kwargs),
                    do_profile=is_profiling(),
                )
                await context.in_queue.put(queue_input)
                wrapped_result = await context.out_queue.get()

            if isinstance(wrapped_result, Exception):
                raise wrapped_result

            return wrapped_result

        return wrapper

    return decorator
