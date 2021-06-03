# pylint: disable=redefined-outer-name
import uuid
import pytest

from simcore_service_director_v2.modules.dynamic_sidecar.monitor.models import (
    ServiceStateReply,
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
        hostname="some host",
        port=1222,
        service_key="simcore/services/dynamic/test-image",
        service_tag="1.0.1",
        paths_mapping=paths_mapping,
        compose_spec=None,
        target_container=None,
        dynamic_sidecar_network_name="some_network_name",
        simcore_traefik_zone="main",
        service_port=3000,
    )


def test_service_reply_make_status(node_uuid: str, monitor_data: MonitorData):
    status = ServiceStateReply.make_status(
        node_uuid=node_uuid,
        monitor_data=monitor_data,
        service_state=ServiceState.RUNNING,
        service_message="",
    )
    print(status)
    assert status
    assert status.dict(exclude_unset=True) == {
        "dynamic_type": "dynamic-sidecar",
        "service_state": "running",
        "service_message": "",
        "published_port": 80,
        "service_uuid": node_uuid,
        "service_key": "simcore/services/dynamic/test-image",
        "service_version": "1.0.1",
        "service_host": "some service",
        "service_port": "3000",
        "service_basepath": "",
        "entry_point": "",
    }


def test_service_reply_error_status(node_uuid: str):
    error_status = ServiceStateReply.error_status(node_uuid)
    print(error_status)
    assert error_status
    assert error_status.dict(exclude_unset=True) == {
        "dynamic_type": "dynamic-sidecar",
        "service_state": "error",
        "service_message": f"Could not find a service for node_uuid={node_uuid}",
    }
