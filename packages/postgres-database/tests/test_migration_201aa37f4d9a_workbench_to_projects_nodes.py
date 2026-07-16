# pylint: disable=protected-access
"""Unit tests for the workbench -> projects_nodes migration transform.

Validates the pure helper ``_workbench_node_to_db_values`` exhaustively so the
data migration is reliable regardless of:
- key casing (camelCase alias vs snake_case column)
- empty containers / empty strings / zero / False
- missing optional fields (-> NULL) vs missing required fields (-> error)
- unknown keys (-> error) and explicitly-ignored keys (silently skipped)
- column-set drift between the migration and the current ``projects_nodes`` model.
"""

import importlib
import json

import pytest
from simcore_postgres_database.models.projects_nodes import projects_nodes

MIGRATION_MODULE = (
    "simcore_postgres_database.migration.versions.201aa37f4d9a_migrate_workbench_column_to_projects_nodes"
)

_migration = importlib.import_module(MIGRATION_MODULE)
_workbench_node_to_db_values = _migration._workbench_node_to_db_values
_ALL_NODE_COLUMNS = _migration._ALL_NODE_COLUMNS
_JSONB_COLUMNS = _migration._JSONB_COLUMNS
_SCALAR_COLUMNS = _migration._SCALAR_COLUMNS
_ALIAS_TO_COLUMN = _migration._ALIAS_TO_COLUMN
_DROPPED_BY_LATER_MIGRATIONS: frozenset[str] = frozenset({"thumbnail"})


_PROJECT = "00000000-0000-0000-0000-000000000001"
_NODE = "11111111-1111-1111-1111-111111111111"


def _required_minimal() -> dict:
    return {"key": "k", "version": "1.0.0", "label": "L"}


# --- column-inventory guard --------------------------------------------------


def test_migration_column_set_matches_live_model():
    """If a column is added/removed on projects_nodes, the migration must be updated."""
    live_columns = {c.name for c in projects_nodes.columns}
    # excluded: managed by the table (PK, FK, timestamps, required_resources default)
    live_data_columns = live_columns - {
        "project_node_id",
        "project_uuid",
        "node_id",
        "created",
        "modified",
        "required_resources",
    }
    assert live_data_columns == _ALL_NODE_COLUMNS - _DROPPED_BY_LATER_MIGRATIONS


# --- happy paths -------------------------------------------------------------


def test_required_minimal_only_produces_nulls_for_optionals():
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, _required_minimal())
    assert errors == []
    assert row is not None
    assert row["project_uuid"] == _PROJECT
    assert row["node_id"] == _NODE
    assert row["key"] == "k"
    for col in _ALL_NODE_COLUMNS - {"key", "version", "label"}:
        assert row[col] is None, col


@pytest.mark.parametrize(
    "alias, column",
    sorted(_ALIAS_TO_COLUMN.items()),
)
def test_each_alias_maps_to_its_column(alias: str, column: str):
    sample: object = {"x": 1} if column in _JSONB_COLUMNS else "scalar"
    node = _required_minimal() | {alias: sample}
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, node)
    assert errors == [], (alias, errors)
    assert row is not None
    expected = json.dumps(sample) if column in _JSONB_COLUMNS else sample
    assert row[column] == expected


def test_snake_case_keys_pass_through():
    node = _required_minimal() | {
        "input_access": {"a": "r"},
        "run_hash": "abc",
        "boot_options": {"k": "v"},
    }
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, node)
    assert errors == []
    assert row is not None
    assert row["input_access"] == json.dumps({"a": "r"})
    assert row["run_hash"] == "abc"
    assert row["boot_options"] == json.dumps({"k": "v"})


def test_snake_case_wins_over_camelcase_when_both_present():
    node = _required_minimal() | {
        "inputAccess": {"camel": True},
        "input_access": {"snake": True},
    }
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, node)
    assert errors == []
    assert row is not None
    assert row["input_access"] == json.dumps({"snake": True})


# --- edge values are preserved (the original `or` bug) ----------------------


@pytest.mark.parametrize(
    "value",
    [
        pytest.param({}, id="empty_dict"),
        pytest.param([], id="empty_list"),
        pytest.param("", id="empty_string"),
        pytest.param(0, id="zero"),
        pytest.param(False, id="false"),
    ],
)
def test_falsy_jsonb_values_are_preserved_not_nulled(value):
    node = _required_minimal() | {"inputs": value, "outputs": value, "state": value}
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, node)
    assert errors == []
    assert row is not None
    assert row["inputs"] == json.dumps(value)
    assert row["outputs"] == json.dumps(value)
    assert row["state"] == json.dumps(value)


def test_explicit_none_becomes_null_for_jsonb():
    node = _required_minimal() | {"inputs": None, "state": None}
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, node)
    assert errors == []
    assert row is not None
    assert row["inputs"] is None
    assert row["state"] is None


def test_scalar_zero_and_false_preserved():
    node = _required_minimal() | {"progress": 0, "thumbnail": ""}
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, node)
    assert errors == []
    assert row is not None
    assert row["progress"] == 0
    assert row["thumbnail"] == ""


# --- error paths -------------------------------------------------------------


@pytest.mark.parametrize("missing", ["key", "version", "label"])
def test_missing_required_field_is_error(missing: str):
    node = _required_minimal()
    del node[missing]
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, node)
    assert row is None
    assert len(errors) == 1
    assert missing in errors[0]


@pytest.mark.parametrize("falsy", [None, ""])
def test_required_field_falsy_is_error(falsy):
    node = _required_minimal() | {"label": falsy}
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, node)
    assert row is None
    assert "label" in errors[0]


def test_unknown_key_is_error_not_silently_dropped():
    node = _required_minimal() | {"mysteryField": 1}
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, node)
    assert row is None
    assert "mysteryField" in errors[0]


def test_position_key_is_silently_ignored():
    # position is deprecated and dropped (not migrated)
    node = _required_minimal() | {"position": {"x": 1, "y": 2}}
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, node)
    assert errors == []
    assert row is not None


def test_non_dict_node_data_is_error():
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, "not-a-dict")  # type: ignore[arg-type]
    assert row is None
    assert "not a dictionary" in errors[0]


# --- column coverage sanity -------------------------------------------------


def test_every_column_is_present_in_output_row():
    row, errors = _workbench_node_to_db_values(_PROJECT, _NODE, _required_minimal())
    assert errors == []
    assert row is not None
    expected_keys = {"project_uuid", "node_id"} | _ALL_NODE_COLUMNS
    assert set(row.keys()) == expected_keys
