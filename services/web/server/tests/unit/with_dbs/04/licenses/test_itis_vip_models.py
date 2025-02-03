# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from faker import Faker
from pydantic import ValidationError
from pytest_simcore.helpers.faker_factories import (
    random_itis_vip_available_download_item,
)
from simcore_service_webserver.licenses._itis_vip_models import (
    ItisVipData,
    _feature_descriptor_to_dict,
)


def test_pre_validator_feature_descriptor_to_dict():
    # Makes sure the regex used here, which is vulnerable to polynomial runtime due to backtracking, cannot lead to denial of service.
    with pytest.raises(ValidationError) as err_info:
        _feature_descriptor_to_dict("a" * 10000 + ": " + "b" * 10000)
    assert err_info.value.errors()[0]["type"] == "string_too_long"


def test_model(faker: Faker):

    available_download = random_itis_vip_available_download_item(
        identifier=0,
        features_functionality="Posable",
        faker=faker,
    )

    vip_data = ItisVipData.model_validate(available_download)

    print(vip_data.model_dump(by_alias=True))
