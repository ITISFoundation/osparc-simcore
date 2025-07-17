from models_library.api_schemas_webserver.users import (
    MyProfileRestGet,
)
from models_library.api_schemas_webserver.users_preferences import Preference
from models_library.groups import AccessRightsDict, Group, GroupsByTypeTuple
from models_library.users import MyProfile
from pydantic import TypeAdapter


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
