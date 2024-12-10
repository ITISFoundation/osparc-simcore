import models_library.groups
import pytest
import simcore_postgres_database.models.groups
from faker import Faker
from models_library.api_schemas_webserver._base import OutputSchema
from models_library.api_schemas_webserver.groups import (
    GroupCreate,
    GroupGet,
    GroupUpdate,
    GroupUserAdd,
    GroupUserGet,
)
from models_library.groups import (
    AccessRightsDict,
    Group,
    GroupMember,
    GroupTypeInModel,
    StandardGroupCreate,
    StandardGroupUpdate,
)
from models_library.utils.enums import enum_to_dict
from pydantic import ValidationError


def test_models_library_and_postgress_database_enums_are_equivalent():
    # For the moment these two libraries they do not have a common library to share these
    # basic types so we test here that they are in sync

    assert enum_to_dict(
        simcore_postgres_database.models.groups.GroupType
    ) == enum_to_dict(models_library.groups.GroupTypeInModel)


def test_sanitize_legacy_data():
    users_group_1 = GroupGet.model_validate(
        {
            "gid": "27",
            "label": "A user",
            "description": "A very special user",
            "thumbnail": "",  # <--- empty strings
            "accessRights": {"read": True, "write": False, "delete": False},
        }
    )

    assert users_group_1.thumbnail is None

    users_group_2 = GroupGet.model_validate(
        {
            "gid": "27",
            "label": "A user",
            "description": "A very special user",
            "thumbnail": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAPgAAADMCAMAAABp5J",  # <--- encoded thumbnail are discarded
            "accessRights": {"read": True, "write": False, "delete": False},
        }
    )

    assert users_group_2.thumbnail is None

    assert users_group_1 == users_group_2


def test_output_schemas_from_models(faker: Faker):
    # output :  schema <- model
    assert issubclass(GroupGet, OutputSchema)
    domain_model = Group(
        gid=1,
        name=faker.word(),
        description=faker.sentence(),
        group_type=GroupTypeInModel.STANDARD,
        thumbnail=None,
    )
    output_schema = GroupGet.from_model(
        domain_model,
        access_rights=AccessRightsDict(read=True, write=False, delete=False),
    )
    assert output_schema.label == domain_model.name

    # output :  schema <- model
    domain_model = GroupMember(
        id=12,
        name=faker.user_name(),
        email=None,
        first_name=None,
        last_name=None,
        primary_gid=13,
        access_rights=AccessRightsDict(read=True, write=False, delete=False),
    )
    output_schema = GroupUserGet.from_model(user=domain_model)
    assert output_schema.user_name == domain_model.name


def test_input_schemas_to_models(faker: Faker):
    # input : scheam -> model
    input_schema = GroupCreate(
        label=faker.word(), description=faker.sentence(), thumbnail=faker.url()
    )
    domain_model = input_schema.to_model()
    assert isinstance(domain_model, StandardGroupCreate)
    assert domain_model.name == input_schema.label

    # input : scheam -> model
    input_schema = GroupUpdate(label=faker.word())
    domain_model = input_schema.to_model()
    assert isinstance(domain_model, StandardGroupUpdate)
    assert domain_model.name == input_schema.label


def test_group_user_add_options(faker: Faker):
    def _only_one_true(*args):
        return sum(bool(arg) for arg in args) == 1

    input_schema = GroupUserAdd(uid=faker.pyint())
    assert input_schema.uid
    assert _only_one_true(input_schema.uid, input_schema.user_name, input_schema.email)

    input_schema = GroupUserAdd(userName=faker.user_name())
    assert input_schema.user_name
    assert _only_one_true(input_schema.uid, input_schema.user_name, input_schema.email)

    input_schema = GroupUserAdd(email=faker.email())
    assert _only_one_true(input_schema.uid, input_schema.user_name, input_schema.email)

    with pytest.raises(ValidationError):
        GroupUserAdd(userName=faker.user_name(), email=faker.email())
