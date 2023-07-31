# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from copy import deepcopy
from pprint import pformat
from typing import Any, Mapping

import pytest
from models_library.api_schemas_webserver.catalog import (
    ServiceInputGet,
    ServiceOutputGet,
)
from pint import UnitRegistry
from pydantic import BaseModel
from simcore_service_webserver.catalog._handlers import RESPONSE_MODEL_POLICY
from simcore_service_webserver.catalog._units import replace_service_input_outputs


@pytest.fixture(scope="module")
def unit_registry():
    return UnitRegistry()


@pytest.mark.parametrize(
    "model_cls",
    (
        ServiceInputGet,
        ServiceOutputGet,
    ),
)
def test_webserver_catalog_api_models(
    model_cls: type[BaseModel], model_cls_examples: dict[str, Mapping[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"

        # tests export policy w/o errors
        data = model_instance.dict(**RESPONSE_MODEL_POLICY)
        assert model_cls(**data) == model_instance


def test_from_catalog_to_webapi_service(unit_registry: UnitRegistry):

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
        "inputs": {
            "uno": {
                "displayOrder": 0,
                "label": "num",
                "description": "Chosen int",
                "type": "number",
                "defaultValue": 33,
            }
        },
        "outputs": {
            "outFile": {
                "displayOrder": 0,
                "label": "File",
                "unit": "sec",
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
    replace_service_input_outputs(
        webapi_service, unit_registry=unit_registry, **RESPONSE_MODEL_POLICY
    )

    print(json.dumps(webapi_service, indent=2))

    # If units are defined, I want unitShort and unitLong
    assert webapi_service["outputs"]["outFile"]["unit"] == "sec"
    assert webapi_service["outputs"]["outFile"]["unitShort"] == "s"
    assert webapi_service["outputs"]["outFile"]["unitLong"] == "second"

    # if units are NOT defined => must NOT set Long/Short units
    fields = set(webapi_service["inputs"]["uno"].keys())
    assert not fields.intersection({"unit", "unitShort", "unitLong"})

    # Trimmed!
    assert "defaultValue" not in webapi_service["outputs"]["outFile"]

    # All None are trimmed
    for field, value in catalog_service["outputs"]["outFile"].items():
        if field != "defaultValue":
            assert webapi_service["outputs"]["outFile"][field] == value
