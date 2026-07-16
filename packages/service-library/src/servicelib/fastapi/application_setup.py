import functools
from typing import Any, Protocol

from common_library.errors_classes import OsparcErrorMixin
from fastapi import FastAPI


class SetupError(OsparcErrorMixin, RuntimeError): ...


class SetupAlreadyFailedError(SetupError):
    msg_template = "Setup '{name}' already failed previously and cannot be retried"


class _SetupFunc(Protocol):
    __qualname__: str

    def __call__(self, app: FastAPI, *args: Any, **kwargs: Any) -> None: ...


def ensure_single_setup[F: _SetupFunc](setup_func: F) -> F:
    """Makes `setup_func(app, ...)` run at most once per FastAPI app instance.

    If it succeeds, further calls are no-ops. If it fails, it is never
    retried: further calls raise `SetupAlreadyFailedError` instead of
    re-running `setup_func` (which may have non-idempotent side effects,
    e.g. `app.include_router`).
    """
    flag_name = f"_setup_state__{setup_func.__qualname__}"

    @functools.wraps(setup_func)
    def _wrapper(app: FastAPI, *args: Any, **kwargs: Any) -> None:
        state = getattr(app.state, flag_name, None)
        if state is True:
            return
        if isinstance(state, BaseException):
            raise SetupAlreadyFailedError(name=setup_func.__qualname__) from state

        try:
            setup_func(app, *args, **kwargs)
        except Exception as exc:
            setattr(app.state, flag_name, exc)
            raise
        setattr(app.state, flag_name, True)

    return _wrapper  # type: ignore[return-value]
