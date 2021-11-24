from .proxy import get_dynamic_proxy_spec
from .settings import (
    MATCH_SERVICE_VERSION,
    MATCH_SIMCORE_REGISTRY,
    inject_settings_to_create_service_params,
    merge_settings_before_use,
)
from .sidecar import (
    extract_service_port_from_compose_start_spec,
    get_dynamic_sidecar_spec,
)
