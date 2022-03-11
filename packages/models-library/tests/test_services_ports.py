# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pathlib import Path

import yaml
from models_library.services import ServiceDockerData
from pint import Unit, UnitRegistry


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
