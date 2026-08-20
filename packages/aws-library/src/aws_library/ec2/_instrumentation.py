import collections
import functools
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass, field
from typing import Any, ParamSpec, TypeVar

from prometheus_client import CollectorRegistry, Counter, Gauge
from servicelib.instrumentation import MetricsBase
from settings_library.ec2 import EC2Settings

from ._client import SimcoreEC2API
from ._models import EC2InstanceData

type InstanceLabels = tuple[str, ...]
type InstanceLabelExtractor = Callable[[EC2InstanceData], InstanceLabels]

_EC2_INSTANCE_LABELS: tuple[str, ...] = ("instance_type",)


@dataclass
class TrackedGauge:
    gauge: Gauge
    label_extractor: InstanceLabelExtractor
    _tracked_labels: set[InstanceLabels] = field(default_factory=set)

    def update_from_instances(self, instances: Iterable[EC2InstanceData]) -> None:
        instance_counts = collections.Counter(self.label_extractor(i) for i in instances)
        current_labels = set(instance_counts.keys())
        self._tracked_labels.update(current_labels)
        # update the gauge
        for labels, count in instance_counts.items():
            self.gauge.labels(*labels).set(count)
        # set the unused ones to 0
        for labels in self._tracked_labels - current_labels:
            self.gauge.labels(*labels).set(0)


def create_gauge(
    *,
    field_name: str,
    definition: tuple[str, tuple[str, ...]],
    namespace: str,
    subsystem: str,
    registry: CollectorRegistry,
    label_extractor: InstanceLabelExtractor,
) -> TrackedGauge:
    description, labelnames = definition
    return TrackedGauge(
        Gauge(
            name=field_name,
            documentation=description,
            labelnames=labelnames,
            namespace=namespace,
            subsystem=subsystem,
            registry=registry,
        ),
        label_extractor=label_extractor,
    )


P = ParamSpec("P")
R = TypeVar("R")


def _instance_type_from_instance_data(instance_data_list: Iterable[EC2InstanceData], *args, **kwargs) -> list[str]:  # noqa: ARG001 # pylint: disable=unused-argument
    return [i.type for i in instance_data_list]


def _instrumented_ec2_client_method(
    metrics_handler: Callable[[str], None],
    *,
    instance_type_from_method_arguments: Callable[..., list[str]] | None = None,
    instance_type_from_method_return: Callable[..., list[str]] | None = _instance_type_from_instance_data,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]],
    Callable[P, Coroutine[Any, Any, R]],
]:
    """Wraps an async EC2 client method so each call reports the instance types it acted on.

    By default the instance types are extracted from the (list[EC2InstanceData]) method return value
    (e.g. launch_instances); pass instance_type_from_method_arguments instead for methods that receive
    the instances as arguments (e.g. start_instances/stop_instances/terminate_instances).
    """

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


@dataclass(slots=True, kw_only=True)
class EC2ClientMetrics(MetricsBase):
    namespace: str
    launched_instances: Counter = field(init=False)
    started_instances: Counter = field(init=False)
    stopped_instances: Counter = field(init=False)
    terminated_instances: Counter = field(init=False)

    def __post_init__(self) -> None:
        for field_name, description in (
            ("launched_instances", "Number of EC2 instances that were launched"),
            ("started_instances", "Number of EC2 instances that were started"),
            ("stopped_instances", "Number of EC2 instances that were stopped"),
            ("terminated_instances", "Number of EC2 instances that were terminated"),
        ):
            setattr(
                self,
                field_name,
                Counter(
                    f"{field_name}_total",
                    description,
                    labelnames=_EC2_INSTANCE_LABELS,
                    namespace=self.namespace,
                    subsystem=self.subsystem,
                    registry=self.registry,
                ),
            )

    def instance_launched(self, instance_type: str) -> None:
        self.launched_instances.labels(instance_type=instance_type).inc()

    def instance_started(self, instance_type: str) -> None:
        self.started_instances.labels(instance_type=instance_type).inc()

    def instance_stopped(self, instance_type: str) -> None:
        self.stopped_instances.labels(instance_type=instance_type).inc()

    def instance_terminated(self, instance_type: str) -> None:
        self.terminated_instances.labels(instance_type=instance_type).inc()


def instrument_ec2_client(ec2_client: SimcoreEC2API, metrics: EC2ClientMetrics) -> SimcoreEC2API:
    """Wraps all known lifecycle methods of ec2_client so they report to metrics.

    This covers the full SimcoreEC2API instance lifecycle (launch/start/stop/terminate) unconditionally:
    a client only needs to opt in once (see aws_library.ec2.configure_ec2_client's client_factory), and
    any of these methods it starts using later is already instrumented, with no per-caller wiring needed.
    """
    methods_to_instrument: list[tuple[str, Callable[[str], None], Callable[..., list[str]] | None]] = [
        ("launch_instances", metrics.instance_launched, None),
        ("start_instances", metrics.instance_started, _instance_type_from_instance_data),
        ("stop_instances", metrics.instance_stopped, _instance_type_from_instance_data),
        ("terminate_instances", metrics.instance_terminated, _instance_type_from_instance_data),
    ]
    for method_name, metrics_handler, instance_type_from_method_arguments in methods_to_instrument:
        method = getattr(ec2_client, method_name, None)
        if method is None:
            # future-proof: skip methods that may not exist on this SimcoreEC2API version
            continue
        decorated_method = _instrumented_ec2_client_method(
            metrics_handler, instance_type_from_method_arguments=instance_type_from_method_arguments
        )(method)
        setattr(ec2_client, method_name, decorated_method)
    return ec2_client


async def create_instrumented_ec2_client(
    settings: EC2Settings, ec2_client_metrics: EC2ClientMetrics | None
) -> SimcoreEC2API:
    """Creates a SimcoreEC2API client, optionally wired to report to ec2_client_metrics.

    Intended to be used as (or from) the client_factory passed to aws_library.ec2.configure_ec2_client:
    if wiring the already-created client to the metrics fails, the client is closed before the
    error is re-raised, since it otherwise never gets tracked/closed by the caller.
    """
    ec2_client = await SimcoreEC2API.create(settings)
    if ec2_client_metrics is None:
        return ec2_client
    try:
        return instrument_ec2_client(ec2_client, ec2_client_metrics)
    except Exception:
        await ec2_client.close()
        raise
