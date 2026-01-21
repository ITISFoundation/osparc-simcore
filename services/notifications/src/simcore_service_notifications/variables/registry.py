from pydantic import BaseModel

from ..exceptions.errors import VariablesModelNotFoundError
from ..models.template import TemplateRef

VARIABLES_MODELS: dict[TemplateRef, type[BaseModel]] = {}


def register_variables_model(channel: str, template_name: str):
    def _(cls: type[BaseModel]):
        VARIABLES_MODELS[TemplateRef(channel, template_name)] = cls
        return cls

    return _


def get_variables_model(ref: TemplateRef) -> type[BaseModel]:
    variables_model = VARIABLES_MODELS.get(ref)
    if not variables_model:
        raise VariablesModelNotFoundError(template_ref=ref)
    return variables_model
