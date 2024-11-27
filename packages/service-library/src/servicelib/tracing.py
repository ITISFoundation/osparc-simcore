from typing import Final

from opentelemetry import context as otcontext
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from settings_library.tracing import TracingSettings

_tracing_settings: Final[TracingSettings] = TracingSettings.create_from_envs()


LoggingInstrumentor().instrument(set_logging_format=False)


def _is_tracing() -> bool:
    # TODO get this value by inspecting settings
    return True


def get_current() -> otcontext.Context | None:
    if not _is_tracing():
        return None
    return otcontext.get_current()


def attach(context: otcontext.Context | None) -> None:
    if context is not None:
        otcontext.attach(context)


def detach(context: otcontext.Context | None) -> None:
    if context is not None:
        otcontext.detach(context)
