import pytest
from common_library.serialization import model_dump_with_secrets
from pydantic import BaseModel, SecretStr


class Credentials(BaseModel):
    USERNAME: str | None = None
    PASSWORD: SecretStr | None = None


@pytest.mark.parametrize(
    "expected,show_secrets",
    [
        (
            {"USERNAME": "DeepThought", "PASSWORD": "42"},
            True,
        ),
        (
            {"USERNAME": "DeepThought", "PASSWORD": "**********"},
            False,  # hide secrets
        ),
    ],
)
def test_model_dump_with_secrets(expected: dict, show_secrets: bool):
    assert expected == model_dump_with_secrets(Credentials(USERNAME="DeepThought", PASSWORD=SecretStr("42")), show_secrets=show_secrets)
