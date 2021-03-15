import asyncio
from collections import deque
from functools import wraps
from typing import Dict, List

import attr


@attr.s(auto_attribs=True)
class Context:
    in_queue: asyncio.Queue
    out_queue: asyncio.Queue
    initialized: bool


sequential_jobs_contexts = {}


def run_sequentially_in_context(target_args: List[str] = None):
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
            func(1, "else", 3),
            func(1, "here", 3),
        ]
        await asyncio.gather(*functions)

    The following calls will run in parallel, because they have different contexts:

        functions = [
            func(1, "something", 3),
            func(2, "else", 3),
            func(3, "here", 3),
        ]
        await asyncio.gather(*functions)

    """
    target_args = [] if target_args is None else target_args

    def internal(decorated_function):
        def get_context(args, kwargs: Dict) -> Context:
            arg_names = decorated_function.__code__.co_varnames[
                : decorated_function.__code__.co_argcount
            ]
            search_args = dict(zip(arg_names, args))
            search_args.update(kwargs)

            key_parts = deque()
            for arg in target_args:
                if arg not in search_args:
                    message = (
                        f"Expected '{arg}' in '{decorated_function.__name__}'"
                        f" arguments. Got '{search_args}'"
                    )
                    raise ValueError(message)
                key_parts.append(search_args[arg])

            key = ":".join(map(str, key_parts))

            if key not in sequential_jobs_contexts:
                sequential_jobs_contexts[key] = Context(
                    in_queue=asyncio.Queue(),
                    out_queue=asyncio.Queue(),
                    initialized=False,
                )

            return sequential_jobs_contexts[key]

        @wraps(decorated_function)
        async def wrapper(*args, **kwargs):
            context: Context = get_context(args, kwargs)

            if not context.initialized:
                context.initialized = True

                async def worker(in_q: asyncio.Queue, out_q: asyncio.Queue):
                    while True:
                        awaitable = await in_q.get()
                        in_q.task_done()
                        try:
                            result = await awaitable
                        except Exception as e:  # pylint: disable=broad-except
                            result = e
                        await out_q.put(result)

                asyncio.get_event_loop().create_task(
                    worker(context.in_queue, context.out_queue)
                )

            await context.in_queue.put(decorated_function(*args, **kwargs))

            wrapped_result = await context.out_queue.get()
            if isinstance(wrapped_result, Exception):
                raise wrapped_result

            return wrapped_result

        return wrapper

    return internal
