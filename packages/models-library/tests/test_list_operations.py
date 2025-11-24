import pytest
from models_library.list_operations import (
    OrderDirection,
    check_ordering_list,
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
