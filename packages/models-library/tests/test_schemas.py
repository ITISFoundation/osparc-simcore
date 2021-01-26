# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from models_library.schemas.storage_api_models import (
    DatasetMetaData,
    FileLocation,
    FileMetaData,
)


@pytest.mark.parametrize("model_cls", (FileLocation, FileMetaData, DatasetMetaData))
def test_storage_api_models_examples(model_cls):
    examples = model_cls.Config.schema_extra["examples"]

    for index, example in enumerate(examples):
        print(f"{index:-^10}:\n", example)

        model_instance = model_cls(**example)
        assert model_instance
