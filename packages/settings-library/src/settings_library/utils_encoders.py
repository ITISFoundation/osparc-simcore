from functools import partial

from pydantic import BaseModel, SecretStr
from pydantic.json import custom_pydantic_encoder


def create_json_encoder_wo_secrets(model_cls: type[BaseModel]):
    current_encoders = getattr(model_cls.Config, "json_encoders", {})
    return partial(
        custom_pydantic_encoder,
        {
            SecretStr: lambda v: v.get_secret_value(),
            **current_encoders,
        },
    )
