# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from typing import Callable, Dict, Optional

import pytest
from faker import Faker
from models_library.generics import Envelope
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import PageDict, paginate_data
from models_library.utils.models_factory import collect_fields_attrs, copy_model
from pydantic import BaseModel, validator
from pydantic.types import PositiveInt
from yarl import URL

# HELPERS ---------------------------------------------------------------


def assert_same_fields(model_cls, reference_model_cls):

    got_fields = collect_fields_attrs(model_cls)
    expected_fields = collect_fields_attrs(reference_model_cls)

    assert set(got_fields.keys()) == set(expected_fields.keys())

    # FIXME: can be tmp used to debug but cannot compare uuids of
    assert got_fields == expected_fields


def _trim_descriptions(schema: Dict):
    data = {}
    for key in schema:
        if key not in ("description", "title"):
            value = schema[key]
            if isinstance(value, dict):
                value = _trim_descriptions(value)
            data[key] = value
    return data


def _validators_factory() -> Callable:
    """Common validator functions"""

    def name_must_contain_space(v):
        if " " not in v:
            raise ValueError("must contain a space")
        return v.title()

    def passwords_match(v, values, **kwargs):
        pasword = values.get("password")
        if pasword is None:
            raise ValueError("reference password missing")

        if v != pasword:
            raise ValueError("passwords do not match")
        return v

    def username_alphanumeric(v):
        assert v.isalnum(), "must be alphanumeric"
        return v

    _map = {
        "display_name": name_must_contain_space,
        "username": username_alphanumeric,
        "password2": passwords_match,
    }

    def _create(field_name) -> classmethod:
        return validator(field_name, allow_reuse=True)(_map[field_name])

    return _create


create_validator_for = _validators_factory()

#
# NOTE: Rationale of this test-suite
#
# Below we represent different views of a 'user' resource represented with
# different models depending on the context. We have a domain model 'User', that
# is used to exchange internally in the business logic, as well as different
# views used in the request body (e.g. 'UserCreate', 'UserUpdate', ...) or response payload
# (e.g. 'UserGet', 'UserListItem', ...) for CRUD entrypoints in an API.
#
# Note that every context demands not only a different set of fields but also
# different constraints. Those will depend on nature of the parsed data sources
# as well as the guarantees defined on the data captured in the model.
#
# This approach should be applicable to any resource but we find that
# 'user' is a good use case that naturally incorporates many of the variants
# that we have typically encountered.
#
# All these variants have many features in common so the idea is to implement a minimalistic
# policy-based tools that can safely compose them all.
#
# Good examples on how to use model polices can be found
#  in https://fastapi-crudrouter.awtkns.com/schemas or
#  in https://fastapi.tiangolo.com/tutorial/body-updates/#body-updates
#
#
class User(BaseModel):
    """Domain model"""

    id: PositiveInt
    display_name: str
    username: str
    password_hash: str

    # validators when model created in code
    _name_must_contain_space = create_validator_for("display_name")
    _username_alphanumeric = create_validator_for("username")


class UserCreate(BaseModel):
    """in -> Model for body of POST /users"""

    display_name: str
    username: str
    password: str
    password2: str

    # parses json-body from Create request
    _name_must_contain_space = create_validator_for("display_name")
    _username_alphanumeric = create_validator_for("username")
    _passwords_match = create_validator_for("password2")


class UserUpdate(BaseModel):
    """in -> Model for body of PATCH /users/{id}"""

    display_name: Optional[str]
    username: Optional[str]
    password: Optional[str]
    password2: Optional[str]

    # parses json-body from Update request
    _name_must_contain_space = create_validator_for("display_name")
    _username_alphanumeric = create_validator_for("username")
    _passwords_match = create_validator_for("password2")


# Model for body of PUT /users/{id}
UserReplace = UserCreate


class UserGet(BaseModel):
    """<- out Detailed model for response in GET /users/{id}"""

    id: PositiveInt
    display_name: str
    username: str

    # parses from User (i.e. validated domain model)


class UserListItem(BaseModel):
    """<- out Item model for response in GET /users"""

    id: PositiveInt
    username: str

    # parses from User


# FIXTURES ---------------------------------------------------------------


@pytest.fixture
def fake_user(faker: Faker) -> User:
    """a fake domain model of a User resource"""
    return User(
        id=faker.pyint(min_value=1),
        display_name=faker.name(),
        username=faker.user_name(),
        password_hash=faker.md5(),
    )


# TESTS ------------------------------------------------------------------


def test_build_UserCreate_model():
    # In UserCreate, we exclude the primary key
    _BaseUserCreate = copy_model(
        User, name="_BaseUserCreate", exclude={"id", "password_hash"}
    )

    # With the new base, we have everything in User (including validators)
    # except for the primary key, then we just need to extend it to include
    # the second password
    class _UserCreate(_BaseUserCreate):
        """in -> Model for body of POST /users"""

        password: str
        password2: str
        _passwords_match = create_validator_for("password2")

    assert _trim_descriptions(UserCreate.schema()) == _trim_descriptions(
        _UserCreate.schema()
    )

    assert_same_fields(_UserCreate, UserCreate)


def test_build_UserUpdate_model(faker: Faker):
    # model for request body Update method https://google.aip.dev/134 (PATCH)

    # in UserUpdate, is as UserCreate but all optional
    _UserUpdate = copy_model(UserCreate, name="UserUpdate", as_update_model=True)

    assert _trim_descriptions(UserUpdate.schema()) == _trim_descriptions(
        _UserUpdate.schema()
    )
    #
    # SEE insight on how to partially update a model
    # in https://fastapi.tiangolo.com/tutorial/body-updates/#partial-updates-with-patch
    #

    update_change_display = _UserUpdate(display_name=faker.name())
    update_reset_password = _UserUpdate(password="secret", password2="secret")
    update_username = _UserUpdate(username=faker.user_name())


def test_build_UserReplace_model():
    # model for request body Replace method https://google.aip.dev/134

    # Replace is like create but w/o primary key (if it would be defined on the client)
    class _UserReplace(copy_model(User, exclude={"id", "password_hash"})):
        password: str
        password2: str
        _passwords_match = create_validator_for("password2")

    assert _trim_descriptions(UserReplace.schema()) == _trim_descriptions(
        _UserReplace.schema()
    )
    #
    # SEE insights on how to replace a model in
    # https://fastapi.tiangolo.com/tutorial/body-updates/#update-replacing-with-put
    #


def test_build_UserGet_model(fake_user: User):
    # model for response payload of Get method https://google.aip.dev/131

    # if the source is User domain model, then the data
    # is already guaranteed (and we could skip validators)
    # or alternative use UserGet.construct()
    #
    _UserGet = copy_model(
        User,
        name="UserGet",
        exclude={"password_hash"},
        skip_validators=True,
    )

    assert _trim_descriptions(UserGet.schema()) == _trim_descriptions(_UserGet.schema())

    payload_user: Dict = (
        Envelope[_UserGet].parse_data(fake_user).dict(exclude_unset=True)
    )

    # NOTE: this would be the solid way to get a jsonable dict ... but requires fastapi!
    # from fastapi.encoders import jsonable_encoder
    # jsonable_encoder(payload_user)
    #
    print(json.dumps(payload_user, indent=1))


def test_build_UserListItem_model(fake_user: User, faker: Faker):
    # model for response payload of List method https://google.aip.dev/132)

    # Typically a light version of the Get model
    _UserListItem = copy_model(
        UserGet,
        name="UserListItem",
        exclude={"display_name"},
        skip_validators=True,
    )

    assert _trim_descriptions(UserListItem.schema()) == _trim_descriptions(
        _UserListItem.schema()
    )

    #  to build the pagination model, simply apply the Page generic
    assert _trim_descriptions(Page[_UserListItem].schema()) == _trim_descriptions(
        Page[UserListItem].schema()
    )

    # parse stored data
    item_user = _UserListItem.parse_obj(fake_user).dict(exclude_unset=True)

    page: PageDict = paginate_data(
        chunk=[item_user],
        request_url=URL(faker.url()).with_path("/users"),
        total=100,
        limit=1,
        offset=0,
    )
    page_users = Page[_UserListItem].parse_obj(page)
    print(page_users.json(indent=2, exclude_unset=True))
