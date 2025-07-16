import pytest
from models_library.api_schemas_webserver.users import (
    MyPhoneRegister,
    MyProfileRestGet,
    PhoneNumberStr,
)
from models_library.api_schemas_webserver.users_preferences import Preference
from models_library.groups import AccessRightsDict, Group, GroupsByTypeTuple
from models_library.users import MyProfile
from pydantic import TypeAdapter, ValidationError


def test_adapter_from_model_to_schema():
    my_profile = MyProfile.model_validate(MyProfile.model_json_schema()["example"])

    groups = TypeAdapter(list[Group]).validate_python(
        Group.model_json_schema()["examples"]
    )

    ar = AccessRightsDict(read=False, write=False, delete=False)

    my_groups_by_type = GroupsByTypeTuple(
        primary=(groups[1], ar), standard=[(groups[2], ar)], everyone=(groups[0], ar)
    )
    my_product_group = groups[-1], AccessRightsDict(
        read=False, write=False, delete=False
    )
    my_preferences = {"foo": Preference(default_value=3, value=1)}

    MyProfileRestGet.from_domain_model(
        my_profile, my_groups_by_type, my_product_group, my_preferences
    )


@pytest.mark.parametrize(
    "phone",
    ["+41763456789", "+19104630364", "+1 301-304-4567"],
)
def test_valid_phone_numbers(phone: str):
    # This test is used to tune options of PhoneNumberValidator
    assert MyPhoneRegister.model_validate({"phone": phone}).phone == TypeAdapter(
        PhoneNumberStr
    ).validate_python(phone)


@pytest.mark.parametrize(
    "phone",
    [
        "+41763456789",
        "+41 76 345 67 89",
        "tel:+41-76-345-67-89",
    ],
    ids=["E.164", "INTERNATIONAL", "RFC3966"],
)
def test_autoformat_phone_number_to_e164(phone: str):
    # This test is used to tune options of PhoneNumberValidator formatting to E164
    assert TypeAdapter(PhoneNumberStr).validate_python(phone) == "+41763456789"


@pytest.mark.parametrize(
    "phone",
    ["41763456789", "+09104630364", "+1 111-304-4567"],
)
def test_invalid_phone_numbers(phone: str):
    # This test is used to tune options of PhoneNumberValidator
    with pytest.raises(ValidationError):
        MyPhoneRegister.model_validate({"phone": phone})
