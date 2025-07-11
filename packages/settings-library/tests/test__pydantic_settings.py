# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Tests subtle details about pydantic models

This test suite intends to "freeze" some concepts/invariants from pydantic upon which we are going
to build this libraries.

This serves the purpose of both as introduction and as a way to guarantee that future versions of pydantic
would still have these invariants.

"""

from collections.abc import Callable
from typing import Annotated, Any

import pytest
from common_library.basic_types import LogLevel
from common_library.pydantic_fields_extension import is_nullable
from pydantic import (
    AliasChoices,
    AmqpDsn,
    BaseModel,
    Field,
    ImportString,
    PostgresDsn,
    RedisDsn,
    ValidationInfo,
    field_validator,
)
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings, SettingsConfigDict
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from settings_library.application import BaseApplicationSettings


def assert_field_specs(
    model_cls: type[BaseSettings],
    name: str,
    required: bool,
    nullable: bool,
    explicit_default,
):
    info = model_cls.model_fields[name]
    print(info)

    assert info.is_required() == required
    assert is_nullable(info) == nullable

    if info.is_required():
        # in this case, default is not really used
        assert info.default is PydanticUndefined
    else:
        assert info.default == explicit_default


class Settings(BaseSettings):
    VALUE: int
    VALUE_DEFAULT: int = 42

    VALUE_NULLABLE_REQUIRED: int | None = ...  # type: ignore[assignment]
    VALUE_NULLABLE_REQUIRED_AS_WELL: int | None

    VALUE_NULLABLE_DEFAULT_VALUE: int | None = 42
    VALUE_NULLABLE_DEFAULT_NULL: int | None = None

    # Other ways to write down "required" is using ...
    VALUE_REQUIRED_AS_WELL: int = ...  # type: ignore[assignment]

    @field_validator("*", mode="before")
    @classmethod
    def parse_none(cls, v, info: ValidationInfo):
        # WARNING: In nullable fields, envs equal to null or none are parsed as None !!

        if (
            info.field_name
            and is_nullable(dict(cls.model_fields)[info.field_name])
            and isinstance(v, str)
            and v.lower() in ("null", "none")
        ):
            return None
        return v


def test_fields_declarations():
    # NOTE:
    #   - optional = not required => defaults to some explicit or implicit value
    #   - nullable = value 'None' is allowed (term borrowed from sql)

    assert_field_specs(
        Settings,
        "VALUE",
        required=True,
        nullable=False,
        explicit_default=PydanticUndefined,
    )

    assert_field_specs(
        Settings,
        "VALUE_DEFAULT",
        required=False,
        nullable=False,
        explicit_default=42,
    )

    assert_field_specs(
        Settings,
        "VALUE_NULLABLE_REQUIRED",
        required=True,
        nullable=True,
        explicit_default=Ellipsis,
    )

    assert_field_specs(
        Settings,
        "VALUE_NULLABLE_REQUIRED_AS_WELL",
        required=True,
        nullable=True,
        explicit_default=PydanticUndefined,  # <- difference wrt VALUE_NULLABLE_DEFAULT_NULL
    )

    # VALUE_NULLABLE_OPTIONAL interpretation has always been confusing
    #  to me but effectively it is equivalent to VALUE_NULLABLE_DEFAULT_NULL.
    #  The only difference is that in one case the default is implicit and in the other explicit

    assert_field_specs(
        Settings,
        "VALUE_NULLABLE_DEFAULT_VALUE",
        required=False,
        nullable=True,
        explicit_default=42,
    )

    assert_field_specs(
        Settings,
        "VALUE_NULLABLE_DEFAULT_NULL",
        required=False,
        nullable=True,
        explicit_default=None,
    )

    assert_field_specs(
        Settings,
        "VALUE_REQUIRED_AS_WELL",
        required=True,
        nullable=False,
        explicit_default=Ellipsis,
    )


def test_construct(monkeypatch):
    # from __init__
    settings_from_init = Settings(
        VALUE=1,
        VALUE_NULLABLE_REQUIRED=None,
        VALUE_NULLABLE_REQUIRED_AS_WELL=None,
        VALUE_REQUIRED_AS_WELL=32,
    )

    print(settings_from_init.model_dump_json(exclude_unset=True, indent=1))

    # from env vars
    setenvs_from_dict(
        monkeypatch,
        {
            "VALUE": "1",
            "VALUE_ALSO_REQUIRED": "10",
            "VALUE_NULLABLE_REQUIRED": "null",
            "VALUE_NULLABLE_REQUIRED_AS_WELL": "null",
            "VALUE_REQUIRED_AS_WELL": "32",
        },
    )  # WARNING: set this env to None would not work w/o ``parse_none`` validator! bug???

    settings_from_env = Settings()  # type: ignore[call-arg]
    print(settings_from_env.model_dump_json(exclude_unset=True, indent=1))

    assert settings_from_init == settings_from_env

    # mixed
    settings_from_both = Settings(VALUE_NULLABLE_REQUIRED=3)  # type: ignore[call-arg]
    print(settings_from_both.model_dump_json(exclude_unset=True, indent=1))

    assert settings_from_both == settings_from_init.model_copy(
        update={"VALUE_NULLABLE_REQUIRED": 3}
    )


class _TestSettings(BaseApplicationSettings):
    APP_LOGLEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices("APP_LOGLEVEL", "LOG_LEVEL"),
        ),
    ] = LogLevel.WARNING


@pytest.mark.filterwarnings("error")
def test_pydantic_serialization_user_warning(monkeypatch: pytest.MonkeyPatch):
    # This test is exploring the reason for `UserWarning`
    #
    # /python3.11/site-packages/pydantic/main.py:477: UserWarning: Pydantic serializer warnings:
    #     Expected `enum` but got `str` with value `'WARNING'` - serialized value may not be as expected
    #     return self.__pydantic_serializer__.to_json(
    #
    # NOTE: it seems settings.model_dump_json(warnings='none') is not the cause here of `UserWarning`
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = _TestSettings.create_from_envs()
    assert settings.APP_LOGLEVEL == LogLevel.DEBUG
    assert settings.model_dump_json(indent=2)


def test_it():
    class SubModel(BaseModel):
        foo: str = "bar"
        apple: int = 1

    class Settings(BaseSettings):
        auth_key: str = Field(validation_alias="my_auth_key")

        api_key: str = Field(alias="my_api_key")

        redis_dsn: RedisDsn = Field(
            "redis://user:pass@localhost:6379/1",
            validation_alias=AliasChoices("service_redis_dsn", "redis_url"),
        )
        pg_dsn: PostgresDsn = "postgres://user:pass@localhost:5432/foobar"
        amqp_dsn: AmqpDsn = "amqp://user:pass@localhost:5672/"

        special_function: ImportString[Callable[[Any], Any]] = "math.cos"

        # to override domains:
        # export my_prefix_domains='["foo.com", "bar.com"]'
        domains: set[str] = set()

        # to override more_settings:
        # export my_prefix_more_settings='{"foo": "x", "apple": 1}'
        more_settings: SubModel = SubModel()

        model_config = SettingsConfigDict(env_prefix="my_prefix_")

    import math

    assert Settings().model_dump() == {
        "auth_key": "xxx",
        "api_key": "xxx",
        "redis_dsn": RedisDsn("redis://user:pass@localhost:6379/1"),
        "pg_dsn": PostgresDsn("postgres://user:pass@localhost:5432/foobar"),
        "amqp_dsn": AmqpDsn("amqp://user:pass@localhost:5672/"),
        "special_function": math.cos,
        "domains": set(),
        "more_settings": {"foo": "bar", "apple": 1},
    }
