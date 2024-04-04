# pylint: disable=broad-exception-caught
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from faker import Faker
from models_library.rest_payloads import (
    ManyErrors,
    OneError,
    create_error_model_from_validation_error,
    loc_to_jq_filter,
)
from pydantic import BaseModel, ValidationError


class ActivationRequiredError(Exception):
    ...


@pytest.fixture
def generic_exc() -> Exception:
    try:
        msg = "Needs to confirm email firt"
        raise ActivationRequiredError(msg)  # noqa: TRY301
    except Exception as exc:
        return exc


def test_minimal_error_model(faker: Faker):
    minimal_error = OneError(msg=faker.sentence())
    assert minimal_error.msg
    assert not minimal_error.kind
    assert not minimal_error.ctx


def test_error_model_from_generic_exception(faker: Faker, generic_exc: Exception):
    error_from_exception = OneError.from_exception(generic_exc)
    assert error_from_exception.ctx is None


def test_error_model_with_context(faker: Faker, generic_exc: Exception):
    # e.g. HTTP_401_UNAUTHORIZED
    error_with_context = OneError.from_exception(
        generic_exc,
        ctx={"resend_confirmation_url": faker.url()},
    )

    assert error_with_context.kind == "ActivationRequiredError"
    assert error_with_context.ctx


def test_to_jq_query():
    #
    # SEE https://jqlang.github.io/jq/manual/#basic-filters
    #
    # NOTE: Could eventually use https://pypi.org/project/jq/ to process them
    #
    assert loc_to_jq_filter(("a",)) == ".a", "Single field name failed"
    assert loc_to_jq_filter((0,)) == "[0]", "Single index failed"
    assert loc_to_jq_filter(("a", 0)) == ".a[0]", "Field name followed by index failed"
    assert loc_to_jq_filter((0, "a")) == "[0].a", "Index followed by field name failed"
    assert (
        loc_to_jq_filter(("a", 0, "b")) == ".a[0].b"
    ), "Field name, index, field name sequence failed"
    assert (
        loc_to_jq_filter((0, "a", 1)) == "[0].a[1]"
    ), "Index, field name, index sequence failed"
    assert (
        loc_to_jq_filter(("a", 0, "b", 1, "c")) == ".a[0].b[1].c"
    ), "Complex sequence with multiple fields and indices failed"
    assert (
        loc_to_jq_filter(("a", -1)) == ".a[-1]"
    ), "Field name with negative index failed"


class A(BaseModel):
    index: int
    required: bool


class B(BaseModel):
    items: list[A]
    obj: A


@pytest.fixture
def one_error_exc(request: pytest.FixtureRequest) -> ValidationError:
    try:
        B.parse_obj(
            {
                "items": [
                    {"index": 33, "required": True},
                    {"index": "not an int", "required": True},  # `index` not int!
                ],
                "obj": {"index": 42, "required": False},
            }
        )
    except ValidationError as err:
        return err


@pytest.fixture
def many_error_exc(request: pytest.FixtureRequest) -> ValidationError:
    try:
        B.parse_obj(
            {
                "items": [
                    {"index": "not an int", "required": False},  # `index` not int !
                ],
                "obj": {"index": 33},  # `required` missing !
            }
        )
    except ValidationError as err:
        return err


def test_error_model_from_validation_error(
    faker: Faker, one_error_exc: ValidationError
):
    # HTTP_422_UNPROCESSABLE_ENTITY
    error_from_validation = create_error_model_from_validation_error(
        one_error_exc, msg="Unprocessable entity in request"
    )

    assert isinstance(error_from_validation, OneError)


def test_error_model_from_many_validation_error(
    faker: Faker, many_error_exc: ValidationError
):

    # HTTP_422_UNPROCESSABLE_ENTITY
    error_from_validation = create_error_model_from_validation_error(
        many_error_exc, msg="Unprocessable entity in request"
    )

    assert isinstance(error_from_validation, ManyErrors)
