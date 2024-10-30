from typing import Any

import pytest
from models_library.api_schemas_webserver.groups import GroupUserAdd
from pydantic import ValidationError

unset = object()


@pytest.mark.parametrize("uid", [1, None, unset])
@pytest.mark.parametrize("email", ["user@foo.com", None, unset])
def test_uid_or_email_are_set(uid: Any, email: Any):
    kwargs = {}
    if uid != unset:
        kwargs["uid"] = uid
    if email != unset:
        kwargs["email"] = email

    none_are_defined = kwargs.get("uid") is None and kwargs.get("email") is None
    both_are_defined = kwargs.get("uid") is not None and kwargs.get("email") is not None

    if none_are_defined or both_are_defined:
        with pytest.raises(ValidationError, match="not both"):
            GroupUserAdd(**kwargs)
    else:
        got = GroupUserAdd(**kwargs)
        assert bool(got.email) ^ bool(got.uid)
