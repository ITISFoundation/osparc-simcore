from typing import Container, Optional, Type

import sqlalchemy as sa
from pydantic import BaseConfig, BaseModel, Field, create_model


class OrmConfig(BaseConfig):
    orm_mode = True


def sa_table_to_pydantic_model(
    table: sa.Table,
    *,
    config: Type = OrmConfig,
    exclude: Optional[Container[str]] = None,
) -> Type[BaseModel]:

    # NOTE: basically copied from https://github.com/tiangolo/pydantic-sqlalchemy/blob/master/pydantic_sqlalchemy/main.py
    fields = {}
    exclude = exclude or []

    for column in table.columns:
        name = str(column.name)
        if name in exclude:
            continue

        python_type: Optional[type] = None
        if hasattr(column.type, "impl"):
            if hasattr(column.type.impl, "python_type"):
                python_type = column.type.impl.python_type
        elif hasattr(column.type, "python_type"):
            python_type = column.type.python_type
        assert python_type, f"Could not infer python_type for {column}"  # nosec
        default = None
        if column.default is None and not column.nullable:
            default = ...

        if hasattr(column, "doc") and column.doc:
            default = Field(default, description=column.doc)

        fields[name] = (python_type, default)

    # create domain models from db-schemas
    pydantic_model = create_model(
        table.name.capitalize(), __config__=config, **fields  # type: ignore
    )
    assert issubclass(pydantic_model, BaseModel)  # nosec
    return pydantic_model
