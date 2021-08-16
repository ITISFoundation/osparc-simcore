import asyncio
from io import StringIO


def get_loop_info() -> str:
    stream = StringIO()
    for n, task in enumerate(asyncio.all_tasks()):
        prefix = "*" if task == asyncio.current_task() else " "
        print(f"{prefix}{n+1:2d}) {task}", file=stream)
    return stream.getvalue()
