"""Global application state — lives in its own module to avoid circular imports."""

import parse

from .constants import (
    DEFAULT_COMPUTATIONAL_EC2_FORMAT,
    DEFAULT_COMPUTATIONAL_EC2_FORMAT_WORKERS,
    DEFAULT_DYNAMIC_EC2_FORMAT,
    wallet_id_spec,
)
from .models import AppState

state: AppState = AppState(
    dynamic_parser=parse.compile(DEFAULT_DYNAMIC_EC2_FORMAT),
    computational_parser_primary=parse.compile(DEFAULT_COMPUTATIONAL_EC2_FORMAT, {"wallet_id_spec": wallet_id_spec}),
    computational_parser_workers=parse.compile(
        DEFAULT_COMPUTATIONAL_EC2_FORMAT_WORKERS, {"wallet_id_spec": wallet_id_spec}
    ),
)
