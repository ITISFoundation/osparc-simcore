import asyncio
import inspect
from collections.abc import Callable
from typing import Any, Final, NamedTuple, TypeAlias

from models_library.utils.specs_substitution import SubstitutionValue
from pydantic import NonNegativeInt
from servicelib.utils import logged_gather

ContextDict: TypeAlias = dict[str, Any]
ContextGetter: TypeAlias = Callable[[ContextDict], Any]


class CaptureError(ValueError):
    ...


def factory_context_getter(parameter_name: str) -> ContextGetter:
    """Factory that creates a function that gets a context as argument and gets a named parameter

    i.e. create_context_getter("foo")(context) == context["foo"]
    """

    def _get_or_raise(context: ContextDict) -> Any:
        try:
            return context[parameter_name]
        except KeyError as err:
            msg = "Parameter {keyname} missing from substitution context"
            raise CaptureError(msg) from err

    # For context["foo"] -> return operator.methodcaller("__getitem__", keyname)
    # For context.foo -> return operator.attrgetter("project_id")
    return _get_or_raise


class RequestTuple(NamedTuple):
    handler: Callable
    kwargs: dict[str, Any]


def factory_handler(coro: Callable) -> Callable[[ContextDict], RequestTuple]:
    assert inspect.iscoroutinefunction(coro)  # nosec

    def _create(context: ContextDict):
        # NOTE: we could delay this as well ...
        kwargs_from_context = {
            param.name: factory_context_getter(param.name)(context)
            for param in inspect.signature(coro).parameters.values()
        }
        return RequestTuple(handler=coro, kwargs=kwargs_from_context)

    return _create


class OsparcVariablesTable:
    def __init__(self):
        self._variables_getters: dict[str, ContextGetter] = {}

    def register(self, table: dict[str, Callable]):
        assert all(  # nosec
            name.startswith("OSPARC_VARIABLE_") for name in table
        )  # nosec
        self._variables_getters.update(table)

    def register_from_context(self, name: str, context_name: str):
        self.register({name: factory_context_getter(context_name)})

    def register_from_handler(self, name: str):
        def _decorator(coro: Callable):
            assert inspect.iscoroutinefunction(coro)  # nosec
            self.register({name: factory_handler(coro)})

        return _decorator

    def variables_names(self):
        return self._variables_getters.keys()

    def copy(
        self, include: set[str] | None = None, exclude: set[str] | None = None
    ) -> dict[str, ContextGetter]:
        all_ = set(self._variables_getters.keys())
        exclude = exclude or set()
        include = include or all_

        assert exclude.issubset(all_)  # nosec
        assert include.issubset(all_)  # nosec

        selection = include.difference(exclude)
        return {k: self._variables_getters[k] for k in selection}


_HANDLERS_TIMEOUT: Final[NonNegativeInt] = 4


async def resolve_variables_from_context(
    variables_getters: dict[str, ContextGetter],
    context: ContextDict,
    *,
    resolve_in_parallel: bool = True,
) -> dict[str, SubstitutionValue]:
    """Resolves variables given a list of handlers and a context
    containing vars which can be used by the handlers.

    Arguments:
        variables_getters -- mapping of awaitables which resolve the value
        context -- variables which can be passed to the awaitables

    Keyword Arguments:
        resolve_in_parallel -- sometimes the variable_getters cannot be ran in parallel,
            for example due to race conditions,
            for those situations set to False (default: {True})
    """
    # evaluate getters from context values
    pre_environs: dict[str, SubstitutionValue | RequestTuple] = {
        key: fun(context) for key, fun in variables_getters.items()
    }

    environs: dict[str, SubstitutionValue] = {}

    coros = {}
    for key, value in pre_environs.items():
        if isinstance(value, RequestTuple):
            handler, kwargs = value
            coro = handler(**kwargs)
            # extra wrap to control timeout
            coros[key] = asyncio.wait_for(coro, timeout=_HANDLERS_TIMEOUT)
        else:
            environs[key] = value

    # evaluates handlers
    values = await logged_gather(
        *coros.values(),
        max_concurrency=0 if resolve_in_parallel else 1,
    )
    for handler_key, handler_value in zip(coros.keys(), values, strict=True):
        environs[handler_key] = handler_value

    assert set(environs.keys()) == set(variables_getters.keys())  # nosec
    return environs
