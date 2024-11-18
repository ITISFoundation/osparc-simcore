# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

""" Tests subtle details about pydantic models

This test suite intends to "freeze" some concepts/invariants from pydantic upon which we are going
to build this libraries.

This serves the purpose of both as introduction and as a way to guarantee that future versions of pydantic
would still have these invariants.

"""

from common_library.pydantic_fields_extension import is_nullable
from pydantic import ValidationInfo, field_validator
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict


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
            and is_nullable(cls.model_fields[info.field_name])
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
