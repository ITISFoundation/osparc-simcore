# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections import defaultdict

import pytest
from models_library.function_services_catalog._registry import (
    FunctionServices,
    FunctionServiceSettings,
    catalog,
)
from models_library.function_services_catalog._utils import validate_callable_signature
from models_library.function_services_catalog.api import (
    is_function_service,
    iter_service_docker_data,
)
from models_library.services import ServiceMetaDataPublished
from models_library.services_io import ServiceInput, ServiceOutput


@pytest.mark.parametrize(
    "image_metadata", iter_service_docker_data(), ids=lambda obj: obj.name
)
def test_create_frontend_services_metadata(image_metadata):
    assert isinstance(image_metadata, ServiceMetaDataPublished)

    assert is_function_service(image_metadata.key)


def test_catalog_frontend_services_registry():
    registry = {(s.key, s.version): s for s in iter_service_docker_data()}

    for s in registry.values():
        print(s.model_dump_json(exclude_unset=True, indent=1))

    # one version per front-end service?
    versions_per_service = defaultdict(list)
    for s in registry.values():
        versions_per_service[s.key].append(s.version)

    assert not any(len(v) > 1 for v in versions_per_service.values())


def test_catalog_registry(monkeypatch: pytest.MonkeyPatch):
    assert catalog._functions
    assert catalog.settings

    # with dev features
    with monkeypatch.context() as patch:
        patch.setenv("CATALOG_DEV_FEATURES_ENABLED", "1")
        patch.setenv("DIRECTOR_V2_DEV_FEATURES_ENABLED", "0")
        patch.setenv("WEBSERVER_DEV_FEATURES_ENABLED", "0")

        dev_catalog = FunctionServices(settings=FunctionServiceSettings())
        dev_catalog.extend(catalog)

        assert not dev_catalog._skip_dev()
        assert dev_catalog._functions == catalog._functions

    # without dev features
    with monkeypatch.context() as patch:
        patch.setenv("CATALOG_DEV_FEATURES_ENABLED", "0")
        patch.setenv("DIRECTOR_V2_DEV_FEATURES_ENABLED", "0")
        patch.setenv("WEBSERVER_DEV_FEATURES_ENABLED", "0")

        prod_catalog = FunctionServices(settings=FunctionServiceSettings())
        prod_catalog.extend(catalog)

        assert prod_catalog._skip_dev()
        assert prod_catalog._functions == catalog._functions

        prod_services = set(prod_catalog.iter_services_key_version())
        dev_services = set(dev_catalog.iter_services_key_version())

        assert len(prod_services) < len(dev_services)
        assert prod_services.issubset(dev_services)


def test_validate_callable_signature_success():
    """Test that a correctly matching callable passes validation"""

    # Create service inputs/outputs matching _EXAMPLE
    service_inputs = {
        "input_1": ServiceInput(
            label="Input data",
            description="Any code, requirements or data file",
            property_type="data:*/*",
        )
    }

    service_outputs = {
        "output_1": ServiceOutput(
            label="Output data",
            description="All data produced by the script is zipped as output_data.zip",
            property_type="data:*/*",
            file_to_key_map={"output_data.zip": "output_1"},
        )
    }

    # Define a matching callable
    def matching_function(input_data: str) -> str:
        return "processed_data"

    # Should not raise any exception
    validate_callable_signature(matching_function, service_inputs, service_outputs)


def test_validate_callable_signature_parameter_count_mismatch():
    """Test that parameter count mismatch raises ValueError"""

    service_inputs = {
        "input_1": ServiceInput(
            label="Input 1",
            description="First input",
            property_type="number",
        ),
        "input_2": ServiceInput(
            label="Input 2",
            description="Second input",
            property_type="number",
        ),
    }

    service_outputs = {
        "output_1": ServiceOutput(
            label="Output",
            description="Result",
            property_type="number",
        )
    }

    # Function with wrong number of parameters
    def wrong_param_count(only_one_param: float) -> float:
        return only_one_param * 2

    with pytest.raises(
        ValueError, match="Function has 1 parameters but service expects 2 inputs"
    ):
        validate_callable_signature(wrong_param_count, service_inputs, service_outputs)


def test_validate_callable_signature_multiple_outputs_wrong_return_type():
    """Test that multiple outputs with non-tuple/dict return type logs warning"""

    service_inputs = {
        "input_1": ServiceInput(
            label="Input",
            description="Input data",
            property_type="number",
        )
    }

    service_outputs = {
        "output_1": ServiceOutput(
            label="Output 1",
            description="First output",
            property_type="number",
        ),
        "output_2": ServiceOutput(
            label="Output 2",
            description="Second output",
            property_type="string",
        ),
    }

    # Function returning single value instead of tuple/dict for multiple outputs
    def wrong_return_type(input_val: float) -> float:  # Should return tuple or dict
        return input_val * 2

    # Should log warning but not raise exception
    with pytest.warns(None) as warning_list:
        validate_callable_signature(wrong_return_type, service_inputs, service_outputs)


def test_validate_callable_signature_with_example_metadata():
    """Test validation using the example metadata from services_metadata_published.py"""
    from models_library.services_metadata_published import (
        _EXAMPLE,
        _EXAMPLE_W_BOOT_OPTIONS_AND_NO_DISPLAY_ORDER,
    )

    # Create metadata from examples
    example_meta = ServiceMetaDataPublished.model_validate(_EXAMPLE)

    # Define a matching callable for the example
    def example_matching_function(input_1: str) -> str:
        """Function that matches _EXAMPLE metadata"""
        return "output_data.zip"

    # Should pass validation
    validate_callable_signature(
        example_matching_function, example_meta.inputs, example_meta.outputs
    )

    # Test with boot options example
    boot_options_meta = ServiceMetaDataPublished.model_validate(
        _EXAMPLE_W_BOOT_OPTIONS_AND_NO_DISPLAY_ORDER
    )

    # Should also pass validation (same inputs/outputs structure)
    validate_callable_signature(
        example_matching_function, boot_options_meta.inputs, boot_options_meta.outputs
    )


def test_validate_callable_signature_none_implementation():
    """Test that None implementation is handled gracefully"""

    service_inputs = {
        "input_1": ServiceInput(
            label="Input", description="Test", property_type="string"
        )
    }
    service_outputs = {
        "output_1": ServiceOutput(
            label="Output", description="Test", property_type="string"
        )
    }

    # Should not raise any exception
    validate_callable_signature(None, service_inputs, service_outputs)


def test_validate_callable_signature_empty_inputs_outputs():
    """Test validation with empty inputs/outputs"""

    def no_param_function() -> None:
        pass

    # Should pass validation - no inputs expected, no outputs expected
    validate_callable_signature(no_param_function, {}, {})
    validate_callable_signature(no_param_function, None, None)
