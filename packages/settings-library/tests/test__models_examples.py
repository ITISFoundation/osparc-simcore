from typing import Any

import pytest
import settings_library
from pydantic_settings import BaseSettings
from pytest_simcore.pydantic_models import (
    assert_validation_model,
    walk_model_examples_in_package,
)


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(settings_library),
)
def test_all_settings_library_models_config_examples(
    model_cls: type[BaseSettings], example_name: str, example_data: Any
):

    assert (
        model_cls.model_config.get("populate_by_name") is True
    ), f"populate_by_name must be enabled in {model_cls}. It will be deprecated in the future but for now it is required to use aliases in the settings"
    assert (
        model_cls.model_config.get("validate_by_alias") is True
    ), f"validate_by_alias must be enabled in {model_cls}"
    assert (
        model_cls.model_config.get("validate_by_name") is True
    ), f"validate_by_name must be enabled in {model_cls}"

    assert_validation_model(
        model_cls, example_name=example_name, example_data=example_data
    )
