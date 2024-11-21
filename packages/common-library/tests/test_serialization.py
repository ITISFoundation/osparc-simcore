import pytest
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
        Access(
            credentials=Credentials(username="DeepThought", password=SecretStr("42"))
        ),
        show_secrets=show_secrets,
    )
