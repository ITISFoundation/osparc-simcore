""" Automatic creation of pydantic model classes from a sqlalchemy table

SEE: Copied and adapted from https://github.com/tiangolo/pydantic-sqlalchemy/blob/master/pydantic_sqlalchemy/main.py
"""

import json
import warnings
from datetime import datetime
from typing import Any, Callable, Container
from uuid import UUID

import sqlalchemy as sa
import sqlalchemy.sql.functions
from pydantic import BaseConfig, BaseModel, Field, create_model
from pydantic.types import NonNegativeInt
from sqlalchemy import null
from sqlalchemy.sql.schema import Column

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


def _eval_defaults(
    column: Column, pydantic_type: type, *, include_server_defaults: bool = True
):
    """
    Uses some heuristics to determine the default value/factory produced
    parsing both the client and the server (if include_server_defaults==True) defaults
    in the sa model.
    """
    default: Any | None = None
    default_factory: Callable | None = None

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
        assert column.server_default.is_server_default  # type: ignore  # nosec
        #
        # FIXME: Map server's DefaultClauses to correct values
        #   Heuristics based on test against all our tables
        #
        if pydantic_type:
            if issubclass(pydantic_type, list):
                assert column.server_default.arg == "{}"  # type: ignore  # nosec
                default_factory = list
            elif issubclass(pydantic_type, dict):
                assert column.server_default.arg.text.endswith("::jsonb")  # type: ignore  # nosec
                default = json.loads(
                    column.server_default.arg.text.replace("::jsonb", "").replace(  # type: ignore
                        "'", ""
                    )
                )
            elif issubclass(pydantic_type, datetime):
                assert isinstance(  # nosec
                    column.server_default.arg,  # type: ignore
                    (type(null()), sqlalchemy.sql.functions.now),
                )
                default_factory = datetime.now
    return default, default_factory


PolicyCallable = Callable[[Column, Any, type], tuple[Any, type]]


def eval_name_policy(column: Column, default: Any, pydantic_type: type):
    """All string columns including 'uuid' in their name are set as UUIDs"""
    new_default, new_pydantic_type = default, pydantic_type
    if "uuid" in str(column.name).split("_") and pydantic_type == str:
        new_pydantic_type = UUID
        if isinstance(default, str):
            new_default = UUID(default)
    return new_default, new_pydantic_type


DEFAULT_EXTRA_POLICIES = [
    eval_name_policy,
]


def create_pydantic_model_from_sa_table(
    table: sa.Table,
    *,
    config: type = OrmConfig,
    exclude: Container[str] | None = None,
    include_server_defaults: bool = False,
    extra_policies: list[PolicyCallable] | None = None,
) -> type[BaseModel]:
    fields = {}
    exclude = exclude or []
    extra_policies = extra_policies or DEFAULT_EXTRA_POLICIES  # type: ignore

    for column in table.columns:
        name = str(column.name)

        if name in exclude:
            continue

        field_args: dict[str, Any] = {}

        if name in _RESERVED:
            field_args["alias"] = name
            name = f"{table.name.lower()}_{name}"

        # type ---
        pydantic_type: type | None = None
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
        default, default_factory = _eval_defaults(
            column, pydantic_type, include_server_defaults=include_server_defaults
        )

        # Policies based on naming conventions
        #
        # TODO: implement it as a pluggable policy class.
        # Base policy class is abstract interface
        # and user can add as many in a given order in the arguments
        #
        for apply_policy in extra_policies:
            default, pydantic_type = apply_policy(column, default, pydantic_type)

        if default_factory:
            field_args["default_factory"] = default_factory
        else:
            field_args["default"] = default

        if hasattr(column, "doc") and column.doc:
            field_args["description"] = column.doc

        fields[name] = (pydantic_type, Field(**field_args))  # type: ignore

    # create domain models from db-schemas
    pydantic_model: type[BaseModel] = create_model(
        table.name.capitalize(), __config__=config, **fields  # type: ignore
    )
    assert issubclass(pydantic_model, BaseModel)  # nosec
    return pydantic_model
