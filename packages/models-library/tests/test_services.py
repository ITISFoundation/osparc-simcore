# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any, Dict

import pytest
import yaml
from models_library.services import ServiceCommonData, ServiceDockerData
from pint import Unit, UnitRegistry


@pytest.fixture()
def minimal_service_common_data() -> Dict[str, Any]:
    return dict(
        name="this is a nice sample service",
        description="this is the description of the service",
    )


def test_create_minimal_service_common_data(
    minimal_service_common_data: Dict[str, Any]
):
    service = ServiceCommonData(**minimal_service_common_data)

    assert service.name == minimal_service_common_data["name"]
    assert service.description == minimal_service_common_data["description"]
    assert service.thumbnail == None


def test_node_with_empty_thumbnail(minimal_service_common_data: Dict[str, Any]):
    service_data = minimal_service_common_data
    service_data.update({"thumbnail": ""})

    service = ServiceCommonData(**minimal_service_common_data)

    assert service.name == minimal_service_common_data["name"]
    assert service.description == minimal_service_common_data["description"]
    assert service.thumbnail == None


def test_node_with_thumbnail(minimal_service_common_data: Dict[str, Any]):
    service_data = minimal_service_common_data
    service_data.update(
        {
            "thumbnail": "https://www.google.com/imgres?imgurl=http%3A%2F%2Fclipart-library.com%2Fimages%2FpT5ra4Xgc.jpg&imgrefurl=http%3A%2F%2Fclipart-library.com%2Fcool-pictures.html&tbnid=6Cgc0X9Jo24p3M&vet=12ahUKEwiW3Kbd8KruAhUHzaQKHbvtApwQMygAegUIARCaAQ..i&docid=QuGKBFIIEGuLhM&w=1920&h=1080&q=some%20cool%20images&ved=2ahUKEwiW3Kbd8KruAhUHzaQKHbvtApwQMygAegUIARCaAQ"
        }
    )

    service = ServiceCommonData(**minimal_service_common_data)

    assert service.name == minimal_service_common_data["name"]
    assert service.description == minimal_service_common_data["description"]
    assert (
        service.thumbnail
        == "https://www.google.com/imgres?imgurl=http%3A%2F%2Fclipart-library.com%2Fimages%2FpT5ra4Xgc.jpg&imgrefurl=http%3A%2F%2Fclipart-library.com%2Fcool-pictures.html&tbnid=6Cgc0X9Jo24p3M&vet=12ahUKEwiW3Kbd8KruAhUHzaQKHbvtApwQMygAegUIARCaAQ..i&docid=QuGKBFIIEGuLhM&w=1920&h=1080&q=some%20cool%20images&ved=2ahUKEwiW3Kbd8KruAhUHzaQKHbvtApwQMygAegUIARCaAQ"
    )


def test_service_port_units(osparc_simcore_root_dir):
    ureg = UnitRegistry()

    data = yaml.safe_load(
        (
            osparc_simcore_root_dir / "packages/models-library/tests/image-meta.yaml"
        ).read_text()
    )

    service_meta = ServiceDockerData.parse_obj(data)
    for input_nameid, input_meta in service_meta.inputs.items():
        assert input_nameid

        # validation
        valid_unit: Unit = ureg.parse_units(input_meta.unit)
        assert isinstance(valid_unit, Unit)

        assert valid_unit.dimensionless
