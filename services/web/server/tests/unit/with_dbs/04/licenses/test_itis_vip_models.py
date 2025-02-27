# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import datetime
from typing import Any

import pytest
from faker import Faker
from pydantic import ValidationError
from pytest_simcore.helpers.faker_factories import (
    random_itis_vip_available_download_item,
)
from simcore_service_webserver.licenses._itis_vip_models import (
    ItisVipData,
    ItisVipResourceData,
    _feature_descriptor_to_dict,
)


def test_pre_validator_feature_descriptor_to_dict():
    # Makes sure the regex used here, which is vulnerable to polynomial runtime due to backtracking, cannot lead to denial of service.
    with pytest.raises(ValidationError) as err_info:
        _feature_descriptor_to_dict("a" * 10000 + ": " + "b" * 10000)
    assert err_info.value.errors()[0]["type"] == "string_too_long"


@pytest.mark.parametrize(
    "features_str,expected",
    [
        (
            # checks fix: regex expected at least one space after `:`
            "{species:Mouse, functionality:Static, height:95 mm, date: 2012-01-01, name:Male OF1 Mouse, sex:Male, version:1.0, weight:35.5 g}",
            {
                "version": "1.0",
                "weight": "35.5 g",
                "species": "Mouse",
                "functionality": "Static",
            },
        ),
        (
            # Checks spaces before `,` are removed
            "{date: 2012-01-01, name:  Male OF1 Mouse    , sex:Male}",
            {
                "date": datetime.date(2012, 1, 1),
                "name": "Male OF1 Mouse",
                "sex": "Male",
            },
        ),
    ],
)
def test_validation_of_itis_vip_response_model(
    faker: Faker, features_str: str, expected: dict[str, Any]
):

    available_download = random_itis_vip_available_download_item(
        identifier=0,
        fake=faker,
        Features=features_str,
    )

    vip_data = ItisVipData.model_validate(available_download)

    # Checks how features BeforeValidator and parser
    assert {k: vip_data.features[k] for k in expected} == expected

    # Dumped as in the source
    assert vip_data.model_dump(by_alias=True)["Features"] == vip_data.features

    license_resource_data = ItisVipResourceData.model_validate(
        {
            "category_id": "SomeCategoryID",
            "category_display": "This is a resource",
            "source": vip_data,
        }
    )

    assert license_resource_data.source.features == vip_data.features
