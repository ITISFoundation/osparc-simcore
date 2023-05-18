import asyncio
import inspect
from typing import Any, Callable, NamedTuple, TypeAlias

from models_library.utils.specs_substitution import SubstitutionValue

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


async def resolve_session_environs(
    oenvs_table: dict[str, ContextGetter], session_context: ContextDict
):

    # prepares environs from context:
    pre_environs: dict[str, SubstitutionValue | RequestTuple] = {
        key: fun(session_context) for key, fun in oenvs_table.items()
    }

    # execute
    environs: dict[str, SubstitutionValue] = {}

    coros = {}
    for key, value in pre_environs.items():
        if isinstance(value, RequestTuple):
            handler, kwargs = value
            coro = handler(**kwargs)
            # wraps to control timeout
            coros[key] = asyncio.wait_for(coro, timeout=3)
        else:
            environs[key] = value

    values = await asyncio.gather(*coros.values())
    for key, value in zip(coros.keys(), values):
        environs[key] = value

    assert set(environs.keys()) == set(oenvs_table.keys())
    return environs
