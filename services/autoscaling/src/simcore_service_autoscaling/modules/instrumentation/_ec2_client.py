import functools
from collections.abc import Callable, Coroutine, Iterable
from typing import Any, ParamSpec, TypeVar

from aws_library.ec2._client import SimcoreEC2API
from aws_library.ec2._models import EC2InstanceData
from fastapi import FastAPI

from ._core import get_instrumentation

P = ParamSpec("P")
R = TypeVar("R")


def _instrumented_ec2_client_method(
    metrics_handler: Callable[[str], None],
    *,
    instance_type_from_method_arguments: Callable[..., list[str]] | None,
    instance_type_from_method_return: Callable[..., list[str]] | None,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]],
    Callable[P, Coroutine[Any, Any, R]],
]:
    def decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            result = await func(*args, **kwargs)
            if instance_type_from_method_arguments:
                for instance_type in instance_type_from_method_arguments(*args, **kwargs):
                    metrics_handler(instance_type)
            elif instance_type_from_method_return:
                for instance_type in instance_type_from_method_return(result):
                    metrics_handler(instance_type)
            return result

        return wrapper

    return decorator


def _instance_type_from_instance_data(instance_datas: Iterable[EC2InstanceData], *args, **kwargs) -> list[str]:  # noqa: ARG001
    return [i.type for i in instance_datas]


def instrument_ec2_client_methods(app: FastAPI, ec2_client: SimcoreEC2API) -> SimcoreEC2API:
    autoscaling_instrumentation = get_instrumentation(app)
    methods_to_instrument = [
        (
            "launch_instances",
            autoscaling_instrumentation.ec2_client_metrics.instance_launched,
            None,
            _instance_type_from_instance_data,
        ),
        (
            "start_instances",
            autoscaling_instrumentation.ec2_client_metrics.instance_started,
            _instance_type_from_instance_data,
            None,
        ),
        (
            "stop_instances",
            autoscaling_instrumentation.ec2_client_metrics.instance_stopped,
            _instance_type_from_instance_data,
            None,
        ),
        (
            "terminate_instances",
            autoscaling_instrumentation.ec2_client_metrics.instance_terminated,
            _instance_type_from_instance_data,
            None,
        ),
    ]
    for (
        method_name,
        metrics_handler,
        instance_types_from_args,
        instance_types_from_return,
    ) in methods_to_instrument:
        method = getattr(ec2_client, method_name, None)
        assert method is not None  # nosec
        decorated_method = _instrumented_ec2_client_method(
            metrics_handler,
            instance_type_from_method_arguments=instance_types_from_args,
            instance_type_from_method_return=instance_types_from_return,
        )(method)
        setattr(ec2_client, method_name, decorated_method)
    return ec2_client
