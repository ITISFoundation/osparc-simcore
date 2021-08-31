""" Automatic creation of pydantic model classes from a sqlalchemy table

SEE: Copied and adapted from https://github.com/tiangolo/pydantic-sqlalchemy/blob/master/pydantic_sqlalchemy/main.py
"""

import json
import warnings
from datetime import datetime
from typing import Any, Container, Dict, Optional, Type
from uuid import UUID

import sqlalchemy as sa
import sqlalchemy.sql.functions
from pydantic import BaseConfig, BaseModel, Field, create_model
from pydantic.types import NonNegativeInt

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


def create_pydantic_model_from_sa_table(
    table: sa.Table,
    *,
    config: Type = OrmConfig,
    exclude: Optional[Container[str]] = None,
    include_server_defaults: bool = False,
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

        # type ---
        pydantic_type: Optional[type] = None
        if hasattr(column.type, "impl"):
            if hasattr(column.type.impl, "python_type"):
                pydantic_type = column.type.impl.python_type
        elif hasattr(column.type, "python_type"):
            pydantic_type = column.type.python_type

        assert pydantic_type, f"Could not infer pydantic_type for {column}"  # nosec

        # big integer primary keys
        if column.primary_key and issubclass(pydantic_type, int):
            pydantic_type = NonNegativeInt

        # default ----
        default = None
        default_factory = None
        if (
            column.default is None
            and (include_server_defaults and column.server_default is None)
            and not column.nullable
        ):
            default = ...

        if column.default and column.default.is_scalar:
            assert not column.default.is_server_default  # nosec
            default = column.default.arg

        if include_server_defaults and column.server_default:
            assert column.server_default.is_server_default  #  nosec
            #
            # FIXME: Map server's DefaultClauses to correct values
            #   Heuristics based on test against all our tables
            #
            if pydantic_type:
                if issubclass(pydantic_type, list):
                    assert column.server_default.arg == "{}"  # nosec
                    default_factory = list
                elif issubclass(pydantic_type, dict):
                    assert column.server_default.arg.text.endswith("::jsonb")  # nosec
                    default = json.loads(
                        column.server_default.arg.text.replace("::jsonb", "").replace(
                            "'", ""
                        )
                    )
                elif issubclass(pydantic_type, datetime):
                    assert isinstance(  # nosec
                        column.server_default.arg, sqlalchemy.sql.functions.now
                    )
                    default_factory = datetime.now

        # Policies based on naming conventions
        #
        # TODO: implement it as a pluggable policy class.
        # Base policy class is abstract interface
        # and user can add as many in a given order in the arguments
        #
        if "uuid" in name.split("_") and pydantic_type == str:
            pydantic_type = UUID
            if isinstance(default, str):
                default = UUID(default)

        if default_factory:
            field_args["default_factory"] = default_factory
        else:
            field_args["default"] = default

        if hasattr(column, "doc") and column.doc:
            field_args["description"] = column.doc

        fields[name] = (pydantic_type, Field(**field_args))

    # create domain models from db-schemas
    pydantic_model = create_model(
        table.name.capitalize(), __config__=config, **fields  # type: ignore
    )
    assert issubclass(pydantic_model, BaseModel)  # nosec
    return pydantic_model
