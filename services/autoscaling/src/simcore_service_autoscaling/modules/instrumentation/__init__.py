from ._core import get_instrumentation, has_instrumentation, setup
from ._ec2_client import instrument_ec2_client_methods

__all__: tuple[str, ...] = (
    "get_instrumentation",
    "has_instrumentation",
    "instrument_ec2_client_methods",
    "setup",
)

# nopycln: file
