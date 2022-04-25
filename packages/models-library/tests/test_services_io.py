# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path

import pytest
import yaml
from models_library.services import ServiceDockerData, ServiceInput
from pint import Unit, UnitRegistry
from pydantic.tools import schema_of


def test_service_port_units(project_tests_dir: Path):
    ureg = UnitRegistry()

    data = yaml.safe_load((project_tests_dir / "data" / "image-meta.yaml").read_text())
    print(ServiceDockerData.schema_json(indent=2))

    service_meta = ServiceDockerData.parse_obj(data)
    assert service_meta.inputs

    for input_nameid, input_meta in service_meta.inputs.items():
        assert input_nameid

        # validation
        valid_unit: Unit = ureg.parse_units(input_meta.unit)
        assert isinstance(valid_unit, Unit)

        assert valid_unit.dimensionless


def test_build_input_ports_from_json_schemas():

    # builds ServiceInput using json-schema
    port_meta = ServiceInput.from_json_schema(
        port_schema={
            "title": "Distance",
            "minimum": 0,
            "maximum": 10,
            "x_unit": "meter",
            "type": "number",
        }
    )

    assert port_meta.property_type
    assert port_meta.content_schema is not None


@pytest.mark.skip(reason="UNDER DEV")
def test_it():
    # TODO: if type=number or string or integer, add a helper function that transforms it in
    # convert to json-schema like version
    #
    port_meta = ServiceInput.parse_obj(
        {
            "label": "Sleep Time",
            "description": "Time to wait before completion",
            "type": "number",
            "defaultValue": 0,
            "unit": "second",
            "widget": {"type": "TextArea", "details": {"minHeight": 3}},
        }
    )
    assert port_meta.property_type == "number"

    port_meta_converted = ServiceInput.from_json_schema(
        port_schema=schema_of(
            float,
            title=port_meta.description,
            # x_unit=port_meta.unit,
            # description=port_meta.description,
        )
    )
