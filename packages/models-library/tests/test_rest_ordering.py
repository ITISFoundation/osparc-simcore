# pylint: disable=no-self-use

import pickle
from typing import ClassVar, Literal

import pytest
from common_library.json_serialization import json_dumps
from models_library.basic_types import IDStr
from models_library.rest_ordering import (
    OrderBy,
    OrderClause,
    OrderDirection,
    OrderingQueryParams,
    create_ordering_query_model_class,
)
from models_library.rest_pagination import PageQueryParameters
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
        description="Order by field (modified_at|name|description) and direction (asc|desc). "
        "The default sorting order is ascending.",
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


@pytest.mark.xfail(reason="create_ordering_query_model_class.<locals>._OrderBy is still not pickable")
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

    loaded = pickle.loads(data)  # noqa: S301
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
    order_by = TypeAdapter(OrderBy).validate_python(query_model.order_by, from_attributes=True)
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
    class OrderQueryParamsModel(BaseOrderingQueryModel): ...

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
        OrderQueryParamsModel.model_validate({"order_by": {"field": "modified", "direction": "INVALID"}})

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
    assert model.order_by.direction == OrderBy.model_fields.get("direction").default

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


def test_ordering_query_params_parsing():
    """Test OrderingQueryParams parsing from URL query format like ?order_by=-created_at,name,+gender"""

    # Define allowed fields using Literal type
    ValidField = Literal["created_at", "name", "gender"]

    class TestOrderingParams(OrderingQueryParams[ValidField]):
        pass

    # Test parsing from comma-separated string
    params = TestOrderingParams.model_validate({"order_by": "-created_at,name,+gender"})

    assert params.order_by == [
        OrderClause[ValidField](field="created_at", direction=OrderDirection.DESC),
        OrderClause[ValidField](field="name", direction=OrderDirection.ASC),
        OrderClause[ValidField](field="gender", direction=OrderDirection.ASC),
    ]


def test_ordering_query_params_validation_error_with_invalid_fields():
    """Test that OrderingQueryParams raises ValidationError when invalid fields are used"""

    # Define allowed fields using Literal type
    ValidField = Literal["created_at", "name"]

    class TestOrderingParams(OrderingQueryParams[ValidField]):
        pass

    # Test with invalid field should raise ValidationError
    with pytest.raises(ValidationError) as err_info:
        TestOrderingParams.model_validate({"order_by": "-created_at,invalid_field,name"})

    # Verify the validation error details
    exc = err_info.value
    assert exc.error_count() == 1

    error = exc.errors()[0]
    assert error["loc"] == ("order_by", 1, "field")
    assert error["type"] == "literal_error"
    assert error["input"] == "invalid_field"


# ----- New tests: OrderingQueryParams as replacement for create_ordering_query_model_class -----


class TestOrderingQueryParamsFieldMapping:
    """Tests for the _field_name_map feature that remaps API field names to DB column names."""

    def test_field_name_map_remaps_fields(self):
        ValidField = Literal["modified_at", "name", "description"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            _field_name_map: ClassVar[dict[str, str]] = {"modified_at": "modified_column"}

        params = MyOrdering.model_validate({"order_by": "-modified_at,name"})

        assert len(params.order_by) == 2
        assert params.order_by[0].field == "modified_column"
        assert params.order_by[0].direction == OrderDirection.DESC
        assert params.order_by[1].field == "name"
        assert params.order_by[1].direction == OrderDirection.ASC

    def test_field_name_map_empty_by_default(self):
        ValidField = Literal["name", "email"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            pass

        params = MyOrdering.model_validate({"order_by": "name,-email"})

        assert params.order_by[0].field == "name"
        assert params.order_by[1].field == "email"

    def test_field_name_map_validates_before_mapping(self):
        """Literal validation runs BEFORE field mapping, so invalid API names are rejected."""
        ValidField = Literal["modified_at", "name"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            _field_name_map: ClassVar[dict[str, str]] = {"modified_at": "modified"}

        with pytest.raises(ValidationError) as err_info:
            MyOrdering.model_validate({"order_by": "INVALID"})

        error = err_info.value.errors()[0]
        assert error["loc"] == ("order_by", 0, "field")
        assert error["type"] == "literal_error"


class TestOrderingQueryParamsDefaults:
    """Tests for custom default ordering values."""

    def test_empty_default(self):
        ValidField = Literal["name", "email"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            pass

        params = MyOrdering()
        assert params.order_by == []

    def test_custom_default_string(self):
        ValidField = Literal["modified_at", "name"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            _default_order_by: ClassVar[str] = "-modified_at"

        params = MyOrdering()
        assert len(params.order_by) == 1
        assert params.order_by[0].field == "modified_at"
        assert params.order_by[0].direction == OrderDirection.DESC

    def test_custom_default_with_field_map(self):
        ValidField = Literal["modified_at", "name"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            _field_name_map: ClassVar[dict[str, str]] = {"modified_at": "modified_column"}
            _default_order_by: ClassVar[str] = "-modified_at"

        params = MyOrdering()
        assert len(params.order_by) == 1
        assert params.order_by[0].field == "modified_column"
        assert params.order_by[0].direction == OrderDirection.DESC

    def test_explicit_value_overrides_default(self):
        ValidField = Literal["modified_at", "name"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            _default_order_by: ClassVar[str] = "-modified_at"

        params = MyOrdering.model_validate({"order_by": "+name"})
        assert len(params.order_by) == 1
        assert params.order_by[0].field == "name"
        assert params.order_by[0].direction == OrderDirection.ASC


class TestOrderingQueryParamsAsQueryCompatibility:
    """Tests proving OrderingQueryParams is compatible with as_query() from api/specs/web-server/_common.py."""

    def test_no_default_factory_on_order_by(self):
        """as_query() asserts `not field_info.default_factory`.
        OrderingQueryParams must use a plain default, not default_factory.
        """
        ValidField = Literal["name", "email"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            pass

        field_info = MyOrdering.model_fields["order_by"]
        assert field_info.default_factory is None, "default_factory must be None for as_query() compatibility"

    def test_default_is_string(self):
        """The default value should be a string so as_query() can pass it to Query(default=...)."""
        ValidField = Literal["name", "email"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            pass

        field_info = MyOrdering.model_fields["order_by"]
        assert isinstance(field_info.default, str)

    def test_custom_default_is_string(self):
        ValidField = Literal["modified_at", "name"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            _default_order_by: ClassVar[str] = "-modified_at"

        # Base field default is still "" (string), custom default is injected via model_validator
        field_info = MyOrdering.model_fields["order_by"]
        assert isinstance(field_info.default, str)


class TestOrderingQueryParamsParseRequestSimulation:
    """Tests simulating how parse_request_query_parameters_as works:
    it calls model.model_validate(dict(request.query)).
    """

    def test_from_query_dict(self):
        ValidField = Literal["modified_at", "name", "description"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            _field_name_map: ClassVar[dict[str, str]] = {"modified_at": "modified_column"}

        # Simulates dict(request.query) from aiohttp
        data = {"order_by": "-modified_at,name"}
        params = MyOrdering.model_validate(data)

        assert len(params.order_by) == 2
        assert params.order_by[0].field == "modified_column"
        assert params.order_by[0].direction == OrderDirection.DESC
        assert params.order_by[1].field == "name"
        assert params.order_by[1].direction == OrderDirection.ASC

    def test_empty_order_by_from_query(self):
        ValidField = Literal["name", "email"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            pass

        data = {"order_by": ""}
        params = MyOrdering.model_validate(data)
        assert params.order_by == []

    def test_missing_order_by_uses_default(self):
        ValidField = Literal["name", "email"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            _default_order_by: ClassVar[str] = "-email"

        data: dict[str, str] = {}
        params = MyOrdering.model_validate(data)
        assert len(params.order_by) == 1
        assert params.order_by[0].field == "email"
        assert params.order_by[0].direction == OrderDirection.DESC


class TestOrderingQueryParamsComposition:
    """Tests for combining OrderingQueryParams with other query param models via multiple inheritance."""

    def test_compose_with_page_query_parameters(self):
        ValidField = Literal["modified_at", "name"]

        class ListQueryParams(
            PageQueryParameters,
            OrderingQueryParams[ValidField],
        ):
            pass

        data = {"order_by": "-modified_at", "limit": "10", "offset": "5"}
        params = ListQueryParams.model_validate(data)

        assert params.limit == 10
        assert params.offset == 5
        assert len(params.order_by) == 1
        assert params.order_by[0].field == "modified_at"
        assert params.order_by[0].direction == OrderDirection.DESC

    def test_compose_with_page_query_parameters_and_field_map(self):
        ValidField = Literal["modified_at", "name"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            _field_name_map: ClassVar[dict[str, str]] = {"modified_at": "modified_column"}

        class ListQueryParams(
            PageQueryParameters,
            MyOrdering,
        ):
            pass

        data = {"order_by": "-modified_at,name", "limit": "20", "offset": "0"}
        params = ListQueryParams.model_validate(data)

        assert params.limit == 20
        assert params.order_by[0].field == "modified_column"
        assert params.order_by[1].field == "name"

    def test_compose_with_extra_filter_fields(self):
        ValidField = Literal["email", "name"]

        class ListQueryParams(
            PageQueryParameters,
            OrderingQueryParams[ValidField],
        ):
            search: str = ""

        data = {"order_by": "name,-email", "limit": "50", "offset": "0", "search": "john"}
        params = ListQueryParams.model_validate(data)

        assert params.search == "john"
        assert params.limit == 50
        assert len(params.order_by) == 2


class TestOrderingQueryParamsEquivalence:
    """Tests proving OrderingQueryParams can replace create_ordering_query_model_class
    for each production use case pattern.
    """

    def test_folders_pattern(self):
        """Equivalent to folders ordering: modified_at→modified, name (default: -modified_at)"""
        FolderField = Literal["modified_at", "name"]

        class FolderOrdering(OrderingQueryParams[FolderField]):
            _field_name_map: ClassVar[dict[str, str]] = {"modified_at": "modified"}
            _default_order_by: ClassVar[str] = "-modified_at"

        # default
        params = FolderOrdering()
        assert len(params.order_by) == 1
        assert params.order_by[0].field == "modified"
        assert params.order_by[0].direction == OrderDirection.DESC

        # explicit
        params = FolderOrdering.model_validate({"order_by": "name"})
        assert params.order_by[0].field == "name"
        assert params.order_by[0].direction == OrderDirection.ASC

        # invalid
        with pytest.raises(ValidationError):
            FolderOrdering.model_validate({"order_by": "INVALID"})

    def test_users_accounts_pattern(self):
        """Equivalent to users accounts ordering with multiple API-to-column mappings"""
        UserField = Literal["name", "email", "status", "accountRequestedReviewedAt", "preRegistrationCreated"]

        class UserOrdering(OrderingQueryParams[UserField]):
            _field_name_map: ClassVar[dict[str, str]] = {
                "name": "first_name",
                "accountRequestedReviewedAt": "account_request_reviewed_at",
                "preRegistrationCreated": "created",
            }
            _default_order_by: ClassVar[str] = "email"

        # default
        params = UserOrdering()
        assert len(params.order_by) == 1
        assert params.order_by[0].field == "email"

        # multi-field with mapping
        params = UserOrdering.model_validate({"order_by": "-name,email"})
        assert params.order_by[0].field == "first_name"
        assert params.order_by[0].direction == OrderDirection.DESC
        assert params.order_by[1].field == "email"
        assert params.order_by[1].direction == OrderDirection.ASC

        # mapped fields
        params = UserOrdering.model_validate({"order_by": "+preRegistrationCreated"})
        assert params.order_by[0].field == "created"

    def test_computation_runs_pattern(self):
        """Equivalent to computation runs ordering with field mapping"""
        RunField = Literal["submitted_at", "started_at", "ended_at", "state"]

        class RunOrdering(OrderingQueryParams[RunField]):
            _field_name_map: ClassVar[dict[str, str]] = {
                "submitted_at": "created",
                "started_at": "started",
                "ended_at": "ended",
            }
            _default_order_by: ClassVar[str] = "submitted_at"

        # default
        params = RunOrdering()
        assert params.order_by[0].field == "created"

        # multi-field (not possible with old create_ordering_query_model_class!)
        params = RunOrdering.model_validate({"order_by": "-submitted_at,+state"})
        assert len(params.order_by) == 2
        assert params.order_by[0].field == "created"
        assert params.order_by[0].direction == OrderDirection.DESC
        assert params.order_by[1].field == "state"
        assert params.order_by[1].direction == OrderDirection.ASC

    def test_workspaces_pattern(self):
        """Equivalent to workspaces ordering"""
        WsField = Literal["modified_at", "name"]

        class WsOrdering(OrderingQueryParams[WsField]):
            _field_name_map: ClassVar[dict[str, str]] = {"modified_at": "modified"}
            _default_order_by: ClassVar[str] = "-modified_at"

        params = WsOrdering()
        assert params.order_by[0].field == "modified"
        assert params.order_by[0].direction == OrderDirection.DESC


class TestOrderingQueryParamsEdgeCases:
    """Edge cases and robustness tests."""

    def test_pass_through_list_of_dicts(self):
        ValidField = Literal["name", "email"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            pass

        # Already-parsed data (e.g., from internal code)
        data = {"order_by": [{"field": "name", "direction": "asc"}]}
        params = MyOrdering.model_validate(data)
        assert params.order_by[0].field == "name"

    def test_duplicate_fields_are_deduplicated(self):
        ValidField = Literal["name", "email"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            pass

        params = MyOrdering.model_validate({"order_by": "name,name"})
        assert len(params.order_by) == 1
        assert params.order_by[0].field == "name"

    def test_conflicting_directions_raise_error(self):
        ValidField = Literal["name", "email"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            pass

        with pytest.raises(ValidationError):
            MyOrdering.model_validate({"order_by": "name,-name"})

    def test_order_by_model_dump_produces_serializable_output(self):
        ValidField = Literal["name", "email"]

        class MyOrdering(OrderingQueryParams[ValidField]):
            pass

        params = MyOrdering.model_validate({"order_by": "-email,name"})
        dumped = [c.model_dump() for c in params.order_by]
        assert dumped == [
            {"field": "email", "direction": "desc"},
            {"field": "name", "direction": "asc"},
        ]
