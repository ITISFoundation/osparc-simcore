from datetime import UTC, datetime
from uuid import UUID

import pytest
from common_library.json_serialization import json_dumps, json_loads
from common_library.serialization import model_dump_with_secrets
from pydantic import BaseModel, SecretStr


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


@pytest.mark.parametrize("show_secrets", [True, False])
def test_model_dump_with_secrets_json_mode_keeps_secret_visibility(show_secrets: bool):
    node_id = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
    obj = ModelWithJsonUnsafeFields(
        secret=SecretStr("s3cr3t"),
        node_id=node_id,
        created_at=datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC),
        input_port_to_file_id={node_id: "file-1"},
    )

    data = model_dump_with_secrets(obj, show_secrets=show_secrets, mode="json")

    # mode="json" must NOT re-mask the secret when show_secrets=True (regression)
    assert data["secret"] == ("s3cr3t" if show_secrets else "**********")

    # and the result must be fully JSON-safe: UUID/datetime/non-str dict keys converted
    assert data["node_id"] == f"{node_id}"
    assert data["created_at"] == "2024-01-02T03:04:05"
    assert data["input_port_to_file_id"] == {f"{node_id}": "file-1"}

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
