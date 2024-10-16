from collections.abc import Callable
from copy import deepcopy

import pytest
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStartAdapter,
    DynamicServiceStop,
    DynamicServiceStopAdapter,
)
from models_library.projects_nodes_io import NodeID


@pytest.fixture
def get_dynamic_service_start() -> Callable[[NodeID], DynamicServiceStart]:
    def _(node_id: NodeID) -> DynamicServiceStart:
        dict_data = deepcopy(
            DynamicServiceStart.model_config["json_schema_extra"]["example"]
        )
        dict_data["service_uuid"] = f"{node_id}"
        return DynamicServiceStartAdapter.validate_python(dict_data)

    return _


@pytest.fixture
def get_dynamic_service_stop() -> Callable[[NodeID], DynamicServiceStop]:
    def _(node_id: NodeID) -> DynamicServiceStop:
        dict_data = deepcopy(
            DynamicServiceStop.model_config["json_schema_extra"]["example"]
        )
        dict_data["node_id"] = f"{node_id}"
        return DynamicServiceStopAdapter.validate_python(dict_data)

    return _
