# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
from copy import deepcopy

import pytest
from pint import UnitRegistry
from pytest_benchmark.fixture import BenchmarkFixture
from simcore_service_webserver.catalog._controller_rest import RESPONSE_MODEL_POLICY
from simcore_service_webserver.catalog._service_units import (
    replace_service_input_outputs,
)


@pytest.fixture(params=["UnitRegistry", None])
def unit_registry(request: pytest.FixtureRequest) -> UnitRegistry | None:
    return None if request.param is None else UnitRegistry()


def test_from_catalog_to_webapi_service(
    unit_registry: UnitRegistry | None, benchmark: BenchmarkFixture
):

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
                "name": "Foo Bar",
                "email": "foo@fake.com",
                "affiliation": None,
            }
        ],
        "contact": "foo@fake.com",
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
        "owner": "foo@fake.com",
    }

    def _run_async_test():
        s = deepcopy(catalog_service)
        asyncio.get_event_loop().run_until_complete(
            replace_service_input_outputs(
                s, unit_registry=unit_registry, **RESPONSE_MODEL_POLICY
            )
        )
        return s

    result = benchmark(_run_async_test)

    # check result
    got = json.dumps(result, indent=1)

    # If units are defined, I want unitShort and unitLong
    assert result["outputs"]["outFile"]["unit"] == "sec", f"{got=}\n"

    if unit_registry:
        assert result["outputs"]["outFile"]["unitShort"] == "s", f"{got=}\n"
        assert result["outputs"]["outFile"]["unitLong"] == "second", f"{got=}\n"

        # if units are NOT defined => must NOT set Long/Short units
        fields = set(result["inputs"]["uno"].keys())
        assert not fields.intersection({"unit", "unitShort", "unitLong"})

    # Trimmed!
    assert "defaultValue" not in result["outputs"]["outFile"], f"{got=}\n"

    # All None are trimmed
    for field, value in catalog_service["outputs"]["outFile"].items():
        if field != "defaultValue":
            assert result["outputs"]["outFile"][field] == value, f"{got=}\n"
