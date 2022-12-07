from pydantic import BaseModel, Extra


class InputSchema(BaseModel):
    class Config:
        allow_population_by_field_name = False
        extra = Extra.forbid
        allow_mutations = False
