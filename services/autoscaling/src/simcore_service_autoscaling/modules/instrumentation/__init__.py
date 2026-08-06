from ._core import configure_autoscaling_instrumentation, get_instrumentation, has_instrumentation
from ._ec2_client import instrument_ec2_client_methods

__all__: tuple[str, ...] = (
    "configure_autoscaling_instrumentation",
    "get_instrumentation",
    "has_instrumentation",
    "instrument_ec2_client_methods",
)
