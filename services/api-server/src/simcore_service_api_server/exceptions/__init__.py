from . import handlers

setup_exception_handlers = handlers.setup

__all__: tuple[str, ...] = ("setup_exception_handlers",)
