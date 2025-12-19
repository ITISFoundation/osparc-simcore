import pytest
from models_library.api_schemas_webserver.users import (
    MyProfileRestGet,
)
from models_library.api_schemas_webserver.users_preferences import Preference
from models_library.groups import AccessRightsDict, Group, GroupsByTypeTuple
from models_library.users import MyProfile
from pydantic import TypeAdapter


@pytest.mark.parametrize("with_chatbot_user_group", [True, False])
@pytest.mark.parametrize("with_support_group", [True, False])
@pytest.mark.parametrize("with_standard_groups", [True, False])
def test_adapter_from_model_to_schema(
    with_support_group: bool, with_standard_groups: bool, with_chatbot_user_group: bool
):
    my_profile = MyProfile.model_validate(MyProfile.model_json_schema()["example"])

    groups = TypeAdapter(list[Group]).validate_python(
        Group.model_json_schema()["examples"]
    )

    ar = AccessRightsDict(read=False, write=False, delete=False)

    my_groups_by_type = GroupsByTypeTuple(
        primary=(groups[1], ar),
        standard=[(groups[2], ar)] if with_standard_groups else [],
        everyone=(groups[0], ar),
    )
    my_product_group = (
        groups[3],
        AccessRightsDict(read=False, write=False, delete=False),
    )

    my_support_group = groups[4]
    my_chatbot_user_group = groups[5]

    my_preferences = {"foo": Preference(default_value=3, value=1)}

    MyProfileRestGet.from_domain_model(
        my_profile,
        my_groups_by_type,
        my_product_group,
        my_preferences,
        my_support_group if with_support_group else None,
        my_chatbot_user_group if with_chatbot_user_group else None,
    )
