import asyncio
import inspect
from typing import Any, Callable, Final, NamedTuple, TypeAlias

from models_library.utils.specs_substitution import SubstitutionValue
from pydantic import NonNegativeInt, parse_obj_as

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
            raise CaptureError(
                "Parameter {keyname} missing from substitution context"
            ) from err

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


class SessionEnvironmentsTable:
    def __init__(self):
        self._oenv_getters: dict[str, ContextGetter] = {}

    def register(self, table: dict[str, Callable]):
        assert all(  # nosec
            name.startswith("OSPARC_ENVIRONMENT_") for name in table.keys()
        )  # nosec
        self._oenv_getters.update(table)

    def register_from_context(self, name: str, context_name: str):
        self.register({name: factory_context_getter(context_name)})

    def register_from_handler(self, name: str):
        def _decorator(coro: Callable):
            assert inspect.iscoroutinefunction(coro)  # nosec
            self.register({name: factory_handler(coro)})

        return _decorator

    def name_keys(self):
        return self._oenv_getters.keys()

    def copy(
        self, include: set[str] | None = None, exclude: set[str] | None = None
    ) -> dict[str, ContextGetter]:
        all_ = set(self._oenv_getters.keys())
        exclude = exclude or set()
        include = include or all_

        assert exclude.issubset(all_)  # nosec
        assert include.issubset(all_)  # nosec

        selection = include.difference(exclude)
        return {k: self._oenv_getters[k] for k in selection}


_HANDLERS_TIMEOUT: Final[NonNegativeInt] = parse_obj_as(NonNegativeInt, 4)


async def resolve_session_environments(
    oenvs_getters: dict[str, ContextGetter],
    session_context: ContextDict,
) -> dict[str, SubstitutionValue]:

    # evaluate getters from context values
    pre_environs: dict[str, SubstitutionValue | RequestTuple] = {
        key: fun(session_context) for key, fun in oenvs_getters.items()
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
    values = await asyncio.gather(*coros.values())
    for key, value in zip(coros.keys(), values):
        environs[key] = value

    assert set(environs.keys()) == set(oenvs_getters.keys())  # nosec
    return environs
