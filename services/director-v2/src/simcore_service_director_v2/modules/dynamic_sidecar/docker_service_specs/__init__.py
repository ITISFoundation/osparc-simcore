from .spec_dynamic_sidecar import (
    MATCH_SERVICE_VERSION,
    MATCH_SIMCORE_REGISTRY,
    extract_service_port_from_compose_start_spec,
    get_dynamic_sidecar_spec,
    merge_settings_before_use,
)
from .spec_proxy import get_dynamic_proxy_spec
