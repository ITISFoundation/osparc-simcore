# pylint: disable=redefined-outer-name
import uuid

import pytest
from simcore_service_director_v2.models.schemas.dynamic_services import (
    RunningServiceDetails,
)
from simcore_service_director_v2.modules.dynamic_sidecar.monitor.models import (
    MonitorData,
    PathsMapping,
)
from simcore_service_director_v2.modules.dynamic_sidecar.parse_docker_status import (
    ServiceState,
)


@pytest.fixture
def node_uuid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def paths_mapping() -> PathsMapping:
    return PathsMapping(**PathsMapping.Config.schema_extra["examples"])


@pytest.fixture
def monitor_data(node_uuid: str, paths_mapping: PathsMapping) -> MonitorData:
    return MonitorData.assemble(
        service_name="some service",
        node_uuid=node_uuid,
        project_id=uuid.uuid4(),
        user_id=123123,
        hostname="some host",
        port=1222,
        service_key="simcore/services/dynamic/test-image",
        service_tag="1.0.1",
        paths_mapping=paths_mapping,
        compose_spec=None,
        container_http_entry=None,
        dynamic_sidecar_network_name="some_network_name",
        simcore_traefik_zone="main",
        service_port=3000,
    )


def test_running_service_details_make_status(node_uuid: str, monitor_data: MonitorData):
    status = RunningServiceDetails.from_monitoring_status(
        node_uuid=node_uuid,
        monitor_data=monitor_data,
        service_state=ServiceState.RUNNING,
        service_message="starting...",
    )
    print(status)
    assert status
    assert status.dict(exclude_unset=True, by_alias=True) == {
        "boot_type": "V2",
        "service_state": "running",
        "service_message": "starting...",
        "service_uuid": node_uuid,
        "service_key": "simcore/services/dynamic/test-image",
        "service_version": "1.0.1",
        "service_host": "some service",
        "service_port": 3000,
    }
