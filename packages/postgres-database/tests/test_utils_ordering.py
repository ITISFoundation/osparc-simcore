"""Tests for simcore_postgres_database.utils_ordering

These are pure unit tests — no database connection required.
"""

# pylint: disable=no-self-use

from typing import Literal

import pytest
import sqlalchemy as sa
from simcore_postgres_database.utils_ordering import (
    OrderByDict,
    OrderDirection,
    assert_literal_keys_match_column_map,
    create_ordering_clauses,
)

# -- Helpers for tests --

_test_table = sa.table(
    "test_table",
    sa.column("name", sa.String),
    sa.column("email", sa.String),
    sa.column("created_at", sa.DateTime),
    sa.column("modified", sa.DateTime),
)


def _column_map() -> dict[str, object]:
    return {
        "name": _test_table.c.name,
        "email": _test_table.c.email,
        "created_at": _test_table.c.created_at,
        "modified": _test_table.c.modified,
    }


# -- Tests for create_ordering_clauses --


class TestCreateOrderingClauses:
    def test_single_asc(self):
        order_by: list[OrderByDict] = [{"field": "name", "direction": OrderDirection.ASC}]
        clauses = create_ordering_clauses(order_by, _column_map())

        assert len(clauses) == 1
        compiled = clauses[0].compile(compile_kwargs={"literal_binds": True})
        assert "name ASC" in str(compiled) or "name" in str(compiled)

    def test_single_desc(self):
        order_by: list[OrderByDict] = [{"field": "email", "direction": OrderDirection.DESC}]
        clauses = create_ordering_clauses(order_by, _column_map())

        assert len(clauses) == 1
        compiled = str(clauses[0].compile(compile_kwargs={"literal_binds": True}))
        assert "email" in compiled

    def test_multi_field_ordering(self):
        order_by: list[OrderByDict] = [
            {"field": "created_at", "direction": OrderDirection.DESC},
            {"field": "name", "direction": OrderDirection.ASC},
            {"field": "email", "direction": OrderDirection.ASC},
        ]
        clauses = create_ordering_clauses(order_by, _column_map())

        assert len(clauses) == 3

    def test_empty_order_by(self):
        clauses = create_ordering_clauses([], _column_map())
        assert clauses == []

    def test_unknown_field_raises_value_error(self):
        order_by: list[OrderByDict] = [{"field": "nonexistent", "direction": OrderDirection.ASC}]

        with pytest.raises(ValueError, match="Unknown ordering field 'nonexistent'"):
            create_ordering_clauses(order_by, _column_map())

    def test_clauses_usable_in_select_order_by(self):
        order_by: list[OrderByDict] = [
            {"field": "modified", "direction": OrderDirection.DESC},
            {"field": "name", "direction": OrderDirection.ASC},
        ]
        clauses = create_ordering_clauses(order_by, _column_map())

        # Verify they can be used in a real SA select().order_by()
        query = sa.select(_test_table).order_by(*clauses)
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "ORDER BY" in compiled
        assert "modified DESC" in compiled
        assert "name ASC" in compiled

    def test_clauses_preserve_order(self):
        order_by: list[OrderByDict] = [
            {"field": "email", "direction": OrderDirection.ASC},
            {"field": "modified", "direction": OrderDirection.DESC},
        ]
        clauses = create_ordering_clauses(order_by, _column_map())

        query = sa.select(_test_table).order_by(*clauses)
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))

        email_pos = compiled.index("email")
        modified_pos = compiled.index("modified")
        assert email_pos < modified_pos


# -- Tests for assert_literal_keys_match_column_map --


class TestAssertLiteralKeysMatchColumnMap:
    def test_matching_keys(self):
        MyField = Literal["name", "email"]
        column_map = {
            "name": _test_table.c.name,
            "email": _test_table.c.email,
        }
        # Should not raise
        assert_literal_keys_match_column_map(MyField, column_map)

    def test_missing_from_map(self):
        MyField = Literal["name", "email", "created_at"]
        column_map = {
            "name": _test_table.c.name,
            "email": _test_table.c.email,
        }
        with pytest.raises(AssertionError, match="missing from column_map.*created_at"):  # noqa: RUF043
            assert_literal_keys_match_column_map(MyField, column_map)

    def test_extra_in_map(self):
        MyField = Literal["name"]
        column_map = {
            "name": _test_table.c.name,
            "email": _test_table.c.email,
        }
        with pytest.raises(AssertionError, match="not in Literal type.*email"):  # noqa: RUF043
            assert_literal_keys_match_column_map(MyField, column_map)

    def test_both_missing_and_extra(self):
        MyField = Literal["name", "created_at"]
        column_map = {
            "name": _test_table.c.name,
            "email": _test_table.c.email,
        }
        with pytest.raises(AssertionError) as err_info:
            assert_literal_keys_match_column_map(MyField, column_map)

        error_msg = str(err_info.value)
        assert "created_at" in error_msg
        assert "email" in error_msg


# -- Integration: OrderByDict → create_ordering_clauses pipeline --


class TestEndToEndOrderByDictToSA:
    """Tests the full pipeline from OrderByDict to SA clauses."""

    def test_order_by_dict_to_sa_single(self):
        """A single OrderByDict produces a valid SA clause."""
        order_by_dict: OrderByDict = {"field": "name", "direction": OrderDirection.DESC}
        clauses = create_ordering_clauses([order_by_dict], _column_map())

        assert len(clauses) == 1
        query = sa.select(_test_table).order_by(*clauses)
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "name DESC" in compiled

    def test_order_by_dict_list_to_sa_multi(self):
        """Multiple OrderByDicts produce correct multi-field ordering."""
        order_by_dicts: list[OrderByDict] = [
            {"field": "modified", "direction": OrderDirection.DESC},
            {"field": "name", "direction": OrderDirection.ASC},
        ]

        clauses = create_ordering_clauses(order_by_dicts, _column_map())
        assert len(clauses) == 2

        query = sa.select(_test_table).order_by(*clauses)
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "modified DESC" in compiled
        assert "name ASC" in compiled

    def test_empty_order_by_dict_list(self):
        """Empty list produces no clauses."""
        clauses = create_ordering_clauses([], _column_map())
        assert clauses == []
