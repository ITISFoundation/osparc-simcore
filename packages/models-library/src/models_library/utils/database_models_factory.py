""" Automatic creation of pydantic model classes from a sqlalchemy table

SEE: Copied and adapted from https://github.com/tiangolo/pydantic-sqlalchemy/blob/master/pydantic_sqlalchemy/main.py
"""

import warnings
from typing import Any, Container, Dict, Optional, Type
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseConfig, BaseModel, Field, create_model

warnings.warn(
    "This is still a concept under development. "
    "Currently only inteded for testing. "
    "DO NOT USE in production.",
    category=UserWarning,
)


class OrmConfig(BaseConfig):
    orm_mode = True


_RESERVED = {
    "schema",
    # e.g. Field name "schema" shadows a BaseModel attribute; use a different field name with "alias='schema'".
}


def sa_table_to_pydantic_model(
    table: sa.Table,
    *,
    config: Type = OrmConfig,
    exclude: Optional[Container[str]] = None,
) -> Type[BaseModel]:

    fields = {}
    exclude = exclude or []

    for column in table.columns:
        name = str(column.name)

        if name in exclude:
            continue

        field_args: Dict[str, Any] = {}

        if name in _RESERVED:
            field_args["alias"] = name
            name = f"{table.name.lower()}_{name}"

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

        # Policies based on naming conventions
        #
        # TODO: implement it as a pluggable policy class.
        # Base policy class is abstract interface
        # and user can add as many in a given order in the arguments
        #
        if "uuid" in name.split("_") and python_type == str:
            python_type = UUID
            if isinstance(default, str):
                default = UUID(default)

        field_args["default"] = default

        if hasattr(column, "doc") and column.doc:
            field_args["description"] = column.doc

        fields[name] = (python_type, Field(**field_args))

    # create domain models from db-schemas
    pydantic_model = create_model(
        table.name.capitalize(), __config__=config, **fields  # type: ignore
    )
    assert issubclass(pydantic_model, BaseModel)  # nosec
    return pydantic_model
