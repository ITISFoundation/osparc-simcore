from ._core import autoscaling_instrumentation_lifespan, get_instrumentation, has_instrumentation
from ._ec2_client import instrument_ec2_client_methods

__all__: tuple[str, ...] = (
    "autoscaling_instrumentation_lifespan",
    "get_instrumentation",
    "has_instrumentation",
    "instrument_ec2_client_methods",
)

# nopycln: file
