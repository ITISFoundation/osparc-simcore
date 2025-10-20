from typing import Literal

import pytest
from models_library.list_operations import (
    OrderClause,
    OrderDirection,
    check_ordering_list,
    map_order_fields,
    validate_order_fields_with_literals,
)


def test_check_ordering_list_drops_duplicates_silently():
    """Test that check_ordering_list silently drops duplicate entries with same field and direction"""

    # Input with duplicates (same field and direction)
    order_by = [
        ("email", OrderDirection.ASC),
        ("created", OrderDirection.DESC),
        ("email", OrderDirection.ASC),  # Duplicate - should be dropped
        ("name", OrderDirection.ASC),
        ("created", OrderDirection.DESC),  # Duplicate - should be dropped
    ]

    result = check_ordering_list(order_by)

    # Should return unique entries preserving order of first occurrence
    expected = [
        ("email", OrderDirection.ASC),
        ("created", OrderDirection.DESC),
        ("name", OrderDirection.ASC),
    ]

    assert result == expected


def test_check_ordering_list_raises_for_conflicting_directions():
    """Test that check_ordering_list raises ValueError when same field has different directions"""

    # Input with same field but different directions
    order_by = [
        ("email", OrderDirection.ASC),
        ("created", OrderDirection.DESC),
        ("email", OrderDirection.DESC),  # Conflict! Same field, different direction
    ]

    with pytest.raises(ValueError, match="conflicting directions") as exc_info:
        check_ordering_list(order_by)

    error_msg = str(exc_info.value)
    assert "Field 'email' appears with conflicting directions" in error_msg
    assert "asc" in error_msg
    assert "desc" in error_msg


def test_check_ordering_list_empty_input():
    """Test that check_ordering_list handles empty input correctly"""

    result = check_ordering_list([])
    assert result == []


def test_check_ordering_list_no_duplicates():
    """Test that check_ordering_list works correctly when there are no duplicates"""

    order_by = [
        ("email", OrderDirection.ASC),
        ("created", OrderDirection.DESC),
        ("name", OrderDirection.ASC),
    ]

    result = check_ordering_list(order_by)

    # Should return the same list
    assert result == order_by


def test_map_order_fields():
    """Test that map_order_fields correctly maps field names using provided mapping"""

    ValidField = Literal["email", "created_at", "name"]

    order_clauses = [
        OrderClause[ValidField](field="email", direction=OrderDirection.ASC),
        OrderClause[ValidField](field="created_at", direction=OrderDirection.DESC),
        OrderClause[ValidField](field="name", direction=OrderDirection.ASC),
    ]

    field_mapping = {
        "email": "user_email",
        "created_at": "created_timestamp",
        "name": "display_name",
    }

    result = map_order_fields(order_clauses, field_mapping)

    expected = [
        ("user_email", OrderDirection.ASC),
        ("created_timestamp", OrderDirection.DESC),
        ("display_name", OrderDirection.ASC),
    ]

    assert result == expected


def test_map_order_fields_with_unmapped_field():
    """Test that map_order_fields raises KeyError when field is not in mapping"""

    ValidField = Literal["email", "unknown"]

    order_clauses = [
        OrderClause[ValidField](field="email", direction=OrderDirection.ASC),
        OrderClause[ValidField](field="unknown", direction=OrderDirection.DESC),
    ]

    field_mapping = {
        "email": "user_email",
        # "unknown" is missing from mapping
    }

    with pytest.raises(KeyError):
        map_order_fields(order_clauses, field_mapping)


def test_validate_order_fields_with_literals_valid():
    """Test that validate_order_fields_with_literals passes with valid fields and directions"""

    order_by = [
        ("email", "asc"),
        ("created", "desc"),
        ("name", "asc"),
    ]

    valid_fields = {"email", "created", "name"}

    # Should not raise any exception
    validate_order_fields_with_literals(order_by, valid_fields)


def test_validate_order_fields_with_literals_invalid_field():
    """Test that validate_order_fields_with_literals raises ValueError for invalid fields"""

    order_by = [
        ("email", "asc"),
        ("invalid_field", "desc"),
    ]

    valid_fields = {"email", "created"}

    with pytest.raises(ValueError, match="Invalid order_by field") as exc_info:
        validate_order_fields_with_literals(order_by, valid_fields)

    error_msg = str(exc_info.value)
    assert "invalid_field" in error_msg
    assert "Valid fields are" in error_msg


def test_validate_order_fields_with_literals_invalid_direction():
    """Test that validate_order_fields_with_literals raises ValueError for invalid directions"""

    order_by = [
        ("email", "ascending"),  # Invalid direction
        ("created", "desc"),
    ]

    valid_fields = {"email", "created"}

    with pytest.raises(ValueError, match="Invalid order direction") as exc_info:
        validate_order_fields_with_literals(order_by, valid_fields)

    error_msg = str(exc_info.value)
    assert "ascending" in error_msg
    assert "Must be one of" in error_msg
