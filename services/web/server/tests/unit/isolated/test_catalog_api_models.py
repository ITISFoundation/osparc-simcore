# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module


from copy import deepcopy
from pprint import pformat

import pytest
from simcore_service_webserver.catalog_api_handlers import EXPORT_POLICY
from simcore_service_webserver.catalog_api_models import (
    ServiceInputApiOut,
    ServiceOutputApiOut,
    replace_service_input_outputs,
)


@pytest.mark.parametrize(
    "model_cls",
    (
        ServiceInputApiOut,
        ServiceOutputApiOut,
    ),
)
def test_webserver_catalog_api_models(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"

        # tests export policy w/o errors
        data = model_instance.dict(**EXPORT_POLICY)
        assert model_cls(**data) == model_instance


def test_from_catalog_to_webapi_service():

    # Taken from services/catalog/src/simcore_service_catalog/models/schemas/services.py on Feb.2021
    catalog_service = {
        "name": "File Picker",
        "thumbnail": None,
        "description": "File Picker",
        "classifiers": [],
        "quality": {},
        "access_rights": {
            1: {"execute_access": True, "write_access": False},
            4: {"execute_access": True, "write_access": True},
        },
        "key": "simcore/services/frontend/file-picker",
        "version": "1.0.0",
        "integration-version": None,
        "type": "dynamic",
        "badges": None,
        "authors": [
            {
                "name": "Odei Maiz",
                "email": "maiz@itis.swiss",
                "affiliation": None,
            }
        ],
        "contact": "maiz@itis.swiss",
        "inputs": {},
        "outputs": {
            "outFile": {
                "displayOrder": 0,
                "label": "File",
                "description": "Chosen File",
                "type": "data:*/*",
                "fileToKeyMap": None,
                "defaultValue": None,  # <<<<< --- on purpose to emulate old datasets with this invalid field in db
                "widget": None,
            }
        },
        "owner": "maiz@itis.swiss",
    }

    webapi_service = deepcopy(catalog_service)
    replace_service_input_outputs(webapi_service, **EXPORT_POLICY)

    # TODO: dev checks... generalize
    assert webapi_service["outputs"]["outFile"]["unit"] is None
    assert webapi_service["outputs"]["outFile"]["unitShort"] is None
    assert webapi_service["outputs"]["outFile"]["unitLong"] is None

    assert "defaultValue" not in webapi_service["outputs"]["outFile"]

    # the rest must be the same
    for field, value in catalog_service["outputs"]["outFile"].items():
        if field != "defaultValue":
            assert webapi_service["outputs"]["outFile"][field] == value
