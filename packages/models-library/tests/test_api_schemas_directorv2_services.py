# pylint:disable=redefined-outer-name

import pytest
from models_library.api_schemas_directorv2.services import NodeRequirements
from pydantic import ByteSize, ValidationError


def test_node_requirements_accepts_fractional_byte_values():
    # regression: fractional bytes (e.g. 133.12 MiB) must not break ByteSize parsing
    requirements = NodeRequirements.model_validate({"CPU": 1.0, "RAM": 139586437.12, "VRAM": 139586437.12})

    assert requirements.ram == ByteSize(139586437)
    assert requirements.vram == ByteSize(139586437)


def test_node_requirements_accepts_integer_byte_values():
    requirements = NodeRequirements.model_validate({"CPU": 1.0, "RAM": 4194304})

    assert requirements.ram == ByteSize(4194304)
    assert requirements.vram is None


def test_node_requirements_zero_vram_becomes_none():
    requirements = NodeRequirements.model_validate({"CPU": 1.0, "RAM": 4194304, "VRAM": 0.0})

    assert requirements.vram is None


def test_node_requirements_invalid_cpu_raises():
    with pytest.raises(ValidationError):
        NodeRequirements.model_validate({"CPU": 0.0, "RAM": 4194304})
