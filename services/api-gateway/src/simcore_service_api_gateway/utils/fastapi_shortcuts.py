""" Thin wrappers around fastapi interface for convenience

    When to add here a function? These are the goals:
        - overcome common mistakes
        - shortcuts

    And these are the non-goals:
        - replace FastAPI interface

"""
import asyncio
from functools import partial
from typing import Callable

from fastapi import FastAPI


def _wrap_partial(func: Callable, app: FastAPI) -> Callable:
    if asyncio.iscoroutinefunction(func):
        return asyncio.coroutine(partial(func, app))
    return partial(func, app)


def add_event_on_startup(app: FastAPI, func: Callable) -> None:
    callback = _wrap_partial(func, app)
    app.router.add_event_handler("startup", callback)


def add_event_on_shutdown(app: FastAPI, func: Callable) -> None:
    callback = _wrap_partial(func, app)
    app.router.add_event_handler("shutdown", callback)
