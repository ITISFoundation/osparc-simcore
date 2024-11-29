# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path

import yaml
from common_library.json_serialization import json_dumps
from models_library.services import ServiceInput, ServiceMetaDataPublished
from pint import Unit, UnitRegistry


def test_service_port_units(tests_data_dir: Path):
    ureg = UnitRegistry()

    data = yaml.safe_load((tests_data_dir / "metadata-sleeper-2.0.2.yaml").read_text())
    print(json_dumps(ServiceMetaDataPublished.model_json_schema(), indent=2))

    service_meta = ServiceMetaDataPublished.model_validate(data)
    assert service_meta.inputs

    for input_nameid, input_meta in service_meta.inputs.items():
        assert input_nameid

        # validation
        # WARNING: pint>=0.21 parse_units(None) raises!!!
        valid_unit: Unit = ureg.parse_units(input_meta.unit or "")
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
