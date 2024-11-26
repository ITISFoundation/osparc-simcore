import pickle

import pytest
from common_library.json_serialization import json_dumps
from models_library.basic_types import IDStr
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_class,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    Json,
    TypeAdapter,
    ValidationError,
    field_validator,
)


class ReferenceOrderQueryParamsClass(BaseModel):
    # NOTE: this class is a copy of `FolderListSortParams` from
    # services/web/server/src/simcore_service_webserver/folders/_models.py
    # and used as a reference in these tests to ensure the same functionality

    # pylint: disable=unsubscriptable-object
    order_by: Json[OrderBy] = Field(
        default=OrderBy(field=IDStr("modified_at"), direction=OrderDirection.DESC),
        description="Order by field (modified_at|name|description) and direction (asc|desc). The default sorting order is ascending.",
        json_schema_extra={"examples": ['{"field": "name", "direction": "desc"}']},
    )

    @field_validator("order_by", check_fields=False)
    @classmethod
    def _validate_order_by_field(cls, v):
        if v.field not in {
            "modified_at",
            "name",
            "description",
        }:
            msg = f"We do not support ordering by provided field {v.field}"
            raise ValueError(msg)
        if v.field == "modified_at":
            v.field = "modified_column"
        return v

    model_config = ConfigDict(
        extra="forbid",
    )


@pytest.mark.xfail(
    reason="create_ordering_query_model_class.<locals>._OrderBy is still not pickable"
)
def test_pickle_ordering_query_model_class():
    OrderQueryParamsModel = create_ordering_query_model_class(
        ordering_fields={"name", "description"},
        default=OrderBy(field=IDStr("name"), direction=OrderDirection.DESC),
    )

    data = {"order_by": {"field": "name", "direction": "asc"}}
    query_model = OrderQueryParamsModel.model_validate(data)

    # https://docs.pydantic.dev/latest/concepts/serialization/#pickledumpsmodel
    expected = query_model.order_by

    # see https://github.com/ITISFoundation/osparc-simcore/pull/6828
    # FAILURE: raises `AttributeError: Can't pickle local object 'create_ordering_query_model_class.<locals>._OrderBy'`
    data = pickle.dumps(expected)

    loaded = pickle.loads(data)
    assert loaded == expected


def test_conversion_order_by_from_query_to_domain_model():
    OrderQueryParamsModel = create_ordering_query_model_class(
        ordering_fields={"modified_at", "name", "description"},
        default=OrderBy(field=IDStr("modified_at"), direction=OrderDirection.DESC),
    )

    # normal
    data = {"order_by": {"field": "modified_at", "direction": "asc"}}
    query_model = OrderQueryParamsModel.model_validate(data)

    expected_data = data["order_by"]

    assert type(query_model.order_by) is not OrderBy
    assert isinstance(query_model.order_by, OrderBy)

    # NOTE: This does NOT convert to OrderBy but has correct data
    order_by = TypeAdapter(OrderBy).validate_python(
        query_model.order_by, from_attributes=True
    )
    assert type(order_by) is not OrderBy
    assert order_by.model_dump(mode="json") == expected_data

    order_by = OrderBy.model_validate(query_model.order_by.model_dump())
    assert type(order_by) is OrderBy
    assert order_by.model_dump(mode="json") == expected_data

    # NOTE: This does NOT convert to OrderBy but has correct data
    order_by = OrderBy.model_validate(query_model.order_by, from_attributes=True)
    assert type(order_by) is not OrderBy
    assert order_by.model_dump(mode="json") == expected_data

    order_by = OrderBy(**query_model.order_by.model_dump())
    assert type(order_by) is OrderBy
    assert order_by.model_dump(mode="json") == expected_data

    # we should use this !!!
    order_by = OrderBy.model_construct(**query_model.order_by.model_dump())
    assert type(order_by) is OrderBy
    assert order_by.model_dump(mode="json") == expected_data


def test_ordering_query_model_class_factory():
    BaseOrderingQueryModel = create_ordering_query_model_class(
        ordering_fields={"modified_at", "name", "description"},
        default=OrderBy(field=IDStr("modified_at"), direction=OrderDirection.DESC),
        ordering_fields_api_to_column_map={"modified_at": "modified_column"},
    )

    # inherits to add extra post-validator
    class OrderQueryParamsModel(BaseOrderingQueryModel):
        ...

    # normal
    data = {"order_by": {"field": "modified_at", "direction": "asc"}}
    model = OrderQueryParamsModel.model_validate(data)

    assert model.order_by
    assert model.order_by.model_dump() == {
        "field": "modified_column",
        "direction": "asc",
    }

    # test against reference
    expected = ReferenceOrderQueryParamsClass.model_validate(
        {"order_by": json_dumps({"field": "modified_at", "direction": "asc"})}
    )
    assert expected.model_dump() == model.model_dump()


def test_ordering_query_model_class__fails_with_invalid_fields():

    OrderQueryParamsModel = create_ordering_query_model_class(
        ordering_fields={"modified", "name", "description"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
    )

    # fails with invalid field to sort
    with pytest.raises(ValidationError) as err_info:
        OrderQueryParamsModel.model_validate({"order_by": {"field": "INVALID"}})

    error = err_info.value.errors()[0]

    assert error["type"] == "value_error"
    assert "INVALID" in error["msg"]
    assert error["loc"] == ("order_by", "field")


def test_ordering_query_model_class__fails_with_invalid_direction():
    OrderQueryParamsModel = create_ordering_query_model_class(
        ordering_fields={"modified", "name", "description"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
    )

    with pytest.raises(ValidationError) as err_info:
        OrderQueryParamsModel.model_validate(
            {"order_by": {"field": "modified", "direction": "INVALID"}}
        )

    error = err_info.value.errors()[0]

    assert error["type"] == "enum"
    assert error["loc"] == ("order_by", "direction")


def test_ordering_query_model_class__defaults():

    OrderQueryParamsModel = create_ordering_query_model_class(
        ordering_fields={"modified", "name", "description"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
        ordering_fields_api_to_column_map={"modified": "modified_at"},
    )

    # checks  all defaults
    model = OrderQueryParamsModel()
    assert model.order_by is not None
    assert (
        model.order_by.field == "modified_at"  # pylint: disable=no-member
    )  # NOTE that this was mapped!
    assert model.order_by.direction is OrderDirection.DESC  # pylint: disable=no-member

    # partial defaults
    model = OrderQueryParamsModel.model_validate({"order_by": {"field": "name"}})
    assert model.order_by
    assert model.order_by.field == "name"
    assert model.order_by.direction == OrderBy.model_fields["direction"].default

    # direction alone is invalid
    with pytest.raises(ValidationError) as err_info:
        OrderQueryParamsModel.model_validate({"order_by": {"direction": "asc"}})

    error = err_info.value.errors()[0]
    assert error["loc"] == ("order_by", "field")
    assert error["type"] == "missing"


def test_ordering_query_model_with_map():
    OrderQueryParamsModel = create_ordering_query_model_class(
        ordering_fields={"modified", "name", "description"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
        ordering_fields_api_to_column_map={"modified": "some_db_column_name"},
    )

    model = OrderQueryParamsModel.model_validate({"order_by": {"field": "modified"}})
    assert model.order_by
    assert model.order_by.field == "some_db_column_name"


def test_ordering_query_parse_json_pre_validator():

    OrderQueryParamsModel = create_ordering_query_model_class(
        ordering_fields={"modified", "name"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
    )

    bad_json_value = ",invalid json"
    with pytest.raises(ValidationError) as err_info:
        OrderQueryParamsModel.model_validate({"order_by": bad_json_value})

    exc = err_info.value
    assert exc.error_count() == 1
    error = exc.errors()[0]
    assert error["loc"] == ("order_by",)
    assert error["type"] == "value_error"
    assert error["input"] == bad_json_value
