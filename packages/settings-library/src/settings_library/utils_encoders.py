from functools import partial

from pydantic import BaseModel, SecretStr
from pydantic.json import custom_pydantic_encoder


def create_json_encoder_wo_secrets(model_cls: type[BaseModel]):
    """Use to reveal secrtes when seriaizng a model via `.dict()` or `.json()`

    Example:
        model.dict()['my_secret'] == "********"
        show_secrets_encoder = create_json_encoder_wo_secrets(type(model))
        model.dict(encoder=show_secrets_encoder)['my_secret'] == "secret"
    """
    current_encoders = getattr(model_cls.model_config, "json_encoders", {})
    return partial(
        custom_pydantic_encoder,
        {
            SecretStr: lambda v: v.get_secret_value(),
            **current_encoders,
        },
    )
