from pprint import pformat
from typing import Any

import pytest
from models_library.generics import Envelope
from pydantic import BaseModel
from simcore_service_webserver.users_models import (
    AllUsersGroups,
    GroupAccessRights,
    GroupUser,
    ProfileOutput,
    Token,
    UsersGroup,
)


@pytest.mark.parametrize(
    "model_cls",
    (
        GroupAccessRights,
        AllUsersGroups,
        GroupUser,
        ProfileOutput,
        Token,
        UsersGroup,
    ),
)
def test_user_models_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, Any]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"

        model_enveloped = Envelope[model_cls].parse_data(
            model_instance.dict(by_alias=True)
        )
        model_array_enveloped = Envelope[list[model_cls]].parse_data(
            [
                model_instance.dict(by_alias=True),
                model_instance.dict(by_alias=True),
            ]
        )

        assert model_enveloped.error is None
        assert model_array_enveloped.error is None


# class TokenEnveloped(BaseModel):
#    data: Token
#    error: Optional[Any] = None


# class TokensArrayEnveloped(BaseModel):
#    data: list[Token]
#    error: Optional[Any] = None


# class TokenIdEnveloped(BaseModel):
#    data: TokenId
#    error: Optional[Any] = None


# TODO: use envelop here
# class UsersGroupEnveloped(BaseModel):
#    data: UsersGroup
#    error: Optional[Any] = None

# TODO: use envelope here
# class AllUsersGroupsEnveloped(BaseModel):
#    data: AllUsersGroups
#    error: Optional[Any] = None

# class GroupUsersArrayEnveloped(BaseModel):
#    data: list[GroupUser]
#    error: Optional[Any] = None
#
# class GroupUserEnveloped(BaseModel):
#    data: GroupUser
#    error: Optional[Any] = None
#
# class ProfileEnveloped(BaseModel):
#    data: ProfileOutput
#    error: Optional[Any] = None
