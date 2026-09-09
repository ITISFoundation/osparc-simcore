from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from common_library.json_serialization import json_dumps, json_loads
from common_library.serialization import model_dump_with_secrets
from pydantic import AnyUrl, BaseModel, SecretStr
from pydantic_core import Url


class Credentials(BaseModel):
    username: str
    password: SecretStr


class Access(BaseModel):
    credentials: Credentials


@pytest.mark.parametrize(
    "expected,show_secrets",
    [
        (
            {"credentials": {"username": "DeepThought", "password": "42"}},
            True,
        ),
        (
            {"credentials": {"username": "DeepThought", "password": "**********"}},
            False,  # hide secrets
        ),
    ],
)
def test_model_dump_with_secrets(expected: dict, show_secrets: bool):
    assert expected == model_dump_with_secrets(
        Access(credentials=Credentials(username="DeepThought", password=SecretStr("42"))),
        show_secrets=show_secrets,
    )


class ModelWithJsonUnsafeFields(BaseModel):
    secret: SecretStr
    node_id: UUID
    created_at: datetime
    input_port_to_file_id: dict[UUID, str]
    modified_since: timedelta
    any_url: AnyUrl
    url: Url


MODEL_NODE_ID = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
MODEL_CREATED_AT = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)


@pytest.mark.parametrize(
    "show_secrets,expected_secret",
    [
        (True, "s3cr3t"),
        (False, "**********"),
    ],
)
@pytest.mark.parametrize(
    "mode,expected",
    [
        (
            None,
            {
                "any_url": "https://example.com/path?query=1#fragment",
                "created_at": MODEL_CREATED_AT,
                "input_port_to_file_id": {MODEL_NODE_ID: "file-1"},
                "modified_since": 86400.0,
                "node_id": MODEL_NODE_ID,
                "url": "https://example.com/path?query=1#fragment",
            },
        ),
        (
            "json",
            {
                "any_url": "https://example.com/path?query=1#fragment",
                "created_at": "2024-01-02T03:04:05+00:00",
                "input_port_to_file_id": {f"{MODEL_NODE_ID}": "file-1"},
                "modified_since": 86400.0,
                "node_id": f"{MODEL_NODE_ID}",
                "url": "https://example.com/path?query=1#fragment",
            },
        ),
    ],
)
def test_model_dump_with_secrets_json_mode_keeps_secret_visibility(
    show_secrets: bool,
    expected_secret: str,
    mode: str | None,
    expected: dict[str, Any],
):
    node_id = MODEL_NODE_ID
    obj = ModelWithJsonUnsafeFields(
        secret=SecretStr("s3cr3t"),
        node_id=node_id,
        created_at=MODEL_CREATED_AT,
        input_port_to_file_id={node_id: "file-1"},
        modified_since=timedelta(days=1),
        any_url=AnyUrl("https://example.com/path?query=1#fragment"),
        url=Url("https://example.com/path?query=1#fragment"),
    )

    dump_kwargs = {"mode": mode} if mode is not None else {}
    data = model_dump_with_secrets(obj, show_secrets=show_secrets, **dump_kwargs)

    # mode="json" must NOT re-mask the secret when show_secrets=True (regression)
    assert data["secret"] == expected_secret
    assert {k: data[k] for k in expected} == expected

    if mode == "json":
        # round-trips through json without raising
        assert json_loads(json_dumps(data)) == data


class NestedSecret(BaseModel):
    root_key: SecretStr
    input_port_to_file_id: dict[UUID, str]


class ParentWithOptionalNestedSecret(BaseModel):
    user_id: int
    encryption: NestedSecret | None = None


@pytest.mark.parametrize("show_secrets", [True, False])
def test_model_dump_with_secrets_recurses_into_nested_submodel(show_secrets: bool):
    # a single call must unmask secrets inside a nested (optional) submodel, so callers
    # do not need a second explicit dump of the submodel
    node_id = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
    obj = ParentWithOptionalNestedSecret(
        user_id=1,
        encryption=NestedSecret(
            root_key=SecretStr("s3cr3t"),
            input_port_to_file_id={node_id: "file-1"},
        ),
    )

    data = model_dump_with_secrets(obj, show_secrets=show_secrets, mode="json", exclude_unset=True)

    assert data["encryption"]["root_key"] == ("s3cr3t" if show_secrets else "**********")
    assert data["encryption"]["input_port_to_file_id"] == {f"{node_id}": "file-1"}
    assert json_loads(json_dumps(data)) == data


def test_model_dump_with_secrets_omits_unset_optional_nested_submodel():
    obj = ParentWithOptionalNestedSecret(user_id=1)

    data = model_dump_with_secrets(obj, show_secrets=True, mode="json", exclude_unset=True)

    assert data == {"user_id": 1}
