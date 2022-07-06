import functools
import inspect
from ._models import TaskName, MarkOptions, TaskType

MARKED_FUNCTIONS: dict[TaskName, tuple[TaskType, MarkOptions]] = {}

# ANE -> PC/SAN maybe this should just me called `mark`?
def mark_long_running_task(**mark_options):
    def decorator(func):
        if func.__name__ in MARKED_FUNCTIONS:
            raise ValueError(f"A function named '{func.__name__}' was already added")

        positional_args = [
            v.name
            for v in inspect.signature(func).parameters.values()
            if v.default == inspect._empty
        ]

        if not positional_args:
            raise ValueError(
                f"Function '{func.__name__}' must define at least 1 positional argument used for the progress"
            )

        # TODO inject here the rest
        MARKED_FUNCTIONS[func.__name__] = (func, MarkOptions.parse_obj(mark_options))

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator
