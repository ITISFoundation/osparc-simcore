"""Minimal decorator to make a FastAPI app "setup" function idempotent.

Unlike ``functools.cache``, the "already-setup" flag is stored on the
``FastAPI`` app's own ``state`` instead of in the decorator's cache. This
avoids keeping a strong reference to the app (no memory growth or cross-talk
between app instances, e.g. in tests) while still safely no-op'ing on an
accidental second call.
"""

import functools
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI


def ensure_single_setup[F: Callable[..., None]](setup_func: F) -> F:
    flag_name = f"_setup_done__{setup_func.__qualname__}"

    @functools.wraps(setup_func)
    def _wrapper(app: FastAPI, *args: Any, **kwargs: Any) -> None:
        if getattr(app.state, flag_name, False):
            return
        setup_func(app, *args, **kwargs)
        setattr(app.state, flag_name, True)

    return _wrapper  # type: ignore[return-value]
