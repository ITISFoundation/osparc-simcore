# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import sys
from copy import deepcopy
from typing import Any

import pytest
from faker import Faker
from models_library.api_schemas_webserver.auth import AccountRequestInfo
from pytest_simcore.helpers.faker_factories import random_pre_registration_details
from simcore_service_webserver.users._common.schemas import (
    MAX_BYTES_SIZE_EXTRAS,
    PreRegisteredUserGet,
)


@pytest.fixture
def account_request_form(faker: Faker) -> dict[str, Any]:
    # This is AccountRequestInfo.form
    form = {
        "firstName": faker.first_name(),
        "lastName": faker.last_name(),
        "email": faker.email(),
        "phone": faker.phone_number(),
        "company": faker.company(),
        # billing info
        "address": faker.address().replace("\n", ", "),
        "city": faker.city(),
        "postalCode": faker.postcode(),
        "country": faker.country(),
        # extras
        "application": faker.word(),
        "description": faker.sentence(),
        "hear": faker.word(),
        "privacyPolicy": True,
        "eula": True,
    }

    # keeps in sync fields from example and this fixture
    assert set(form) == set(AccountRequestInfo.model_json_schema()["example"]["form"])
    return form


@pytest.mark.parametrize(
    "institution_key",
    [
        "institution",
        "companyName",
        "company",
        "university",
        "universityName",
    ],
)
def test_preuserprofile_parse_model_from_request_form_data(
    account_request_form: dict[str, Any],
    institution_key: str,
):
    data = deepcopy(account_request_form)
    data[institution_key] = data.pop("company")
    data["comment"] = "extra comment"

    # pre-processors
    pre_user_profile = PreRegisteredUserGet(**data)

    print(pre_user_profile.model_dump_json(indent=1))

    # institution aliases
    assert pre_user_profile.institution == account_request_form["company"]

    # extras
    assert {
        "application",
        "description",
        "hear",
        "privacyPolicy",
        "eula",
        "comment",
    } == set(pre_user_profile.extras)
    assert pre_user_profile.extras["comment"] == "extra comment"


def test_preuserprofile_parse_model_without_extras(
    account_request_form: dict[str, Any],
):
    required = {
        f.alias or f_name
        for f_name, f in PreRegisteredUserGet.model_fields.items()
        if f.is_required()
    }
    data = {k: account_request_form[k] for k in required}
    assert not PreRegisteredUserGet(**data).extras


def test_preuserprofile_max_bytes_size_extras_limits(faker: Faker):
    data = random_pre_registration_details(faker)
    data_size = sys.getsizeof(data["extras"])

    assert data_size < MAX_BYTES_SIZE_EXTRAS


@pytest.mark.parametrize(
    "given_name", ["PEDrO-luis", "pedro luis", "   pedro  LUiS   ", "pedro  lUiS   "]
)
def test_preuserprofile_pre_given_names(
    given_name: str,
    account_request_form: dict[str, Any],
):
    account_request_form["firstName"] = given_name
    account_request_form["lastName"] = given_name

    pre_user_profile = PreRegisteredUserGet(**account_request_form)
    print(pre_user_profile.model_dump_json(indent=1))
    assert pre_user_profile.first_name in ["Pedro-Luis", "Pedro Luis"]
    assert pre_user_profile.first_name == pre_user_profile.last_name
