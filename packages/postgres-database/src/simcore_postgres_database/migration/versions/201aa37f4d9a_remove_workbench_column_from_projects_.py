"""Remove workbench column from projects_table

Revision ID: 201aa37f4d9a
Revises: 06eafd25d004
Create Date: 2025-07-22 19:25:42.125196+00:00

"""

import json
import logging
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "201aa37f4d9a"
down_revision = "1c5160923b2a"
branch_labels = None
depends_on = None

_logger = logging.getLogger("alembic.runtime.migration")


# --- projects_nodes column inventory (frozen at this migration) --------------
# Scalar columns persisted as-is.
_SCALAR_COLUMNS: frozenset[str] = frozenset({"key", "version", "label", "progress", "thumbnail", "run_hash", "parent"})
# JSONB columns: values are serialized with json.dumps when not None.
_JSONB_COLUMNS: frozenset[str] = frozenset(
    {
        "input_access",
        "input_nodes",
        "inputs",
        "inputs_required",
        "inputs_units",
        "output_nodes",
        "outputs",
        "state",
        "boot_options",
    }
)
# Columns that must be present and non-None for every node row.
_REQUIRED_COLUMNS: frozenset[str] = frozenset({"key", "version", "label"})
_ALL_NODE_COLUMNS: frozenset[str] = _SCALAR_COLUMNS | _JSONB_COLUMNS


def _snake_to_camel(s: str) -> str:
    head, *tail = s.split("_")
    return head + "".join(p.title() for p in tail)


# camelCase alias -> snake_case projects_nodes column.
_ALIAS_TO_COLUMN: dict[str, str] = {_snake_to_camel(c): c for c in _ALL_NODE_COLUMNS if "_" in c}
# Workbench keys deliberately not migrated into projects_nodes
# (handled elsewhere or no longer persisted).
_IGNORED_WORKBENCH_KEYS: frozenset[str] = frozenset({"position"})


def _migrate_position_to_projects_ui() -> None:
    """Migrate position data from projects.workbench[*].position to projects.ui.workbench[*].position."""

    connection = op.get_bind()

    projects_result = connection.execute(
        sa.text("SELECT uuid, workbench, ui FROM projects WHERE workbench IS NOT NULL")
    )

    migrated_count = 0

    for project_uuid, workbench_json, ui_json in projects_result:
        if not workbench_json:
            continue

        try:
            workbench_data = workbench_json if isinstance(workbench_json, dict) else json.loads(workbench_json)
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(workbench_data, dict):
            continue

        # Collect position data from workbench nodes
        positions: dict[str, Any] = {}
        for node_id, node_data in workbench_data.items():
            if isinstance(node_data, dict) and "position" in node_data:
                pos = node_data["position"]
                if isinstance(pos, dict) and "x" in pos and "y" in pos:
                    positions[node_id] = {"position": pos}

        if not positions:
            continue

        # Merge into existing projects.ui
        try:
            if isinstance(ui_json, dict):
                ui_data = ui_json
            elif ui_json:
                ui_data = json.loads(ui_json)
            else:
                ui_data = {}
        except (json.JSONDecodeError, TypeError):
            ui_data = {}

        existing_workbench_ui = ui_data.get("workbench", {})
        if not isinstance(existing_workbench_ui, dict):
            existing_workbench_ui = {}

        # Only add position if the node doesn't already have one in ui
        for node_id, pos_data in positions.items():
            if node_id not in existing_workbench_ui:
                existing_workbench_ui[node_id] = pos_data
            elif "position" not in existing_workbench_ui[node_id]:
                existing_workbench_ui[node_id]["position"] = pos_data["position"]

        ui_data["workbench"] = existing_workbench_ui

        connection.execute(
            sa.text("UPDATE projects SET ui = :ui_data WHERE uuid = :project_uuid"),
            {"ui_data": json.dumps(ui_data), "project_uuid": project_uuid},
        )
        migrated_count += 1

    _logger.info("Position migration: %d projects had position data migrated to projects.ui", migrated_count)


def _workbench_node_to_db_values(
    project_uuid: str, node_id: str, node_data: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[str]]:
    """Pure transform: single workbench node dict -> projects_nodes row dict.

    Returns ``(row, errors)``. When ``errors`` is non-empty, ``row`` is None.

    Reliability rules:
    - Accepts both camelCase aliases (canonical workbench JSON form) and
      snake_case keys; when both are present for the same field,
      snake_case (the column form) wins.
    - Presence is determined by key membership: empty containers,
      empty strings and zero are preserved. ``None`` and missing keys
      become NULL.
    - Required-column values that are missing or ``None``/``""`` are an
      error.
    - Unknown keys are an error unless explicitly listed in
      ``_IGNORED_WORKBENCH_KEYS``.
    """
    if not isinstance(node_data, dict):
        return None, [f"Project {project_uuid}, Node {node_id}: Node data is not a dictionary"]

    collected: dict[str, Any] = {}
    unknown_keys: list[str] = []
    for raw_key, value in node_data.items():
        if raw_key in _IGNORED_WORKBENCH_KEYS:
            continue
        column = _ALIAS_TO_COLUMN.get(raw_key, raw_key)
        if column not in _ALL_NODE_COLUMNS:
            unknown_keys.append(raw_key)
            continue
        # snake_case (column form) wins over a previously seen camelCase alias
        if column in collected and raw_key != column:
            continue
        collected[column] = value

    if unknown_keys:
        return None, [f"Project {project_uuid}, Node {node_id}: Unknown workbench keys: {sorted(unknown_keys)}"]

    missing_required = [col for col in _REQUIRED_COLUMNS if collected.get(col) in {None, ""}]
    if missing_required:
        return None, [
            f"Project {project_uuid}, Node {node_id}: Missing required fields: {', '.join(sorted(missing_required))}"
        ]

    row: dict[str, Any] = {"project_uuid": project_uuid, "node_id": node_id}
    for column in _ALL_NODE_COLUMNS:
        value = collected.get(column)
        if column in _JSONB_COLUMNS:
            row[column] = None if value is None else json.dumps(value)
        else:
            row[column] = value
    return row, []


def _migrate_workbench_to_projects_nodes() -> None:
    """Migrate nodes from projects.workbench to projects_nodes table."""

    connection = op.get_bind()

    projects_result = connection.execute(sa.text("SELECT uuid, workbench FROM projects WHERE workbench IS NOT NULL"))

    errors: list[str] = []
    upserted_nodes_count = 0

    # Collect all nodes for batch upsert
    batch: list[dict] = []
    batch_size = 500

    for project_uuid, workbench_json in projects_result:
        if not workbench_json:
            continue

        try:
            workbench_data = workbench_json if isinstance(workbench_json, dict) else json.loads(workbench_json)
        except (json.JSONDecodeError, TypeError) as e:
            errors.append(f"Project {project_uuid}: Invalid workbench JSON - {e}")
            continue

        if not isinstance(workbench_data, dict):
            errors.append(f"Project {project_uuid}: Workbench is not a dictionary")
            continue

        for node_id, node_data in workbench_data.items():
            row, node_errors = _workbench_node_to_db_values(project_uuid, node_id, node_data)
            if node_errors:
                errors.extend(node_errors)
                continue
            assert row is not None  # nosec
            batch.append(row)

            if len(batch) >= batch_size:
                upserted_nodes_count += _flush_node_batch(connection, batch)
                batch.clear()

    # Flush remaining
    if batch:
        upserted_nodes_count += _flush_node_batch(connection, batch)

    _logger.info("Migration summary: %d nodes upserted", upserted_nodes_count)

    if errors:
        error_message = f"Migration failed with {len(errors)} errors:\n" + "\n".join(errors)
        _logger.error(error_message)
        raise RuntimeError(error_message)


def _flush_node_batch(connection, batch: list[dict]) -> int:
    """Upsert a batch of nodes using INSERT ... ON CONFLICT."""
    if not batch:
        return 0

    upsert_sql = """
        INSERT INTO projects_nodes (
            project_uuid, node_id, key, version, label, progress, thumbnail,
            input_access, input_nodes, inputs, inputs_required, inputs_units,
            output_nodes, outputs, run_hash, state, parent, boot_options,
            required_resources, created, modified
        ) VALUES (
            :project_uuid, :node_id, :key, :version, :label, :progress, :thumbnail,
            :input_access::jsonb, :input_nodes::jsonb, :inputs::jsonb,
            :inputs_required::jsonb, :inputs_units::jsonb, :output_nodes::jsonb,
            :outputs::jsonb, :run_hash, :state::jsonb, :parent, :boot_options::jsonb,
            '{}'::jsonb, NOW(), NOW()
        )
        ON CONFLICT (project_uuid, node_id) DO UPDATE SET
            key = EXCLUDED.key,
            version = EXCLUDED.version,
            label = EXCLUDED.label,
            progress = EXCLUDED.progress,
            thumbnail = EXCLUDED.thumbnail,
            input_access = EXCLUDED.input_access,
            input_nodes = EXCLUDED.input_nodes,
            inputs = EXCLUDED.inputs,
            inputs_required = EXCLUDED.inputs_required,
            inputs_units = EXCLUDED.inputs_units,
            output_nodes = EXCLUDED.output_nodes,
            outputs = EXCLUDED.outputs,
            run_hash = EXCLUDED.run_hash,
            state = EXCLUDED.state,
            parent = EXCLUDED.parent,
            boot_options = EXCLUDED.boot_options,
            modified = NOW()
    """

    connection.execute(sa.text(upsert_sql), batch)

    return len(batch)
    return len(batch)


def _restore_workbench_from_projects_nodes() -> None:
    """Restore workbench data from projects_nodes table to projects.workbench column."""

    # Get database connection
    connection = op.get_bind()

    # Get all projects that have nodes in projects_nodes
    projects_with_nodes = connection.execute(
        sa.text(
            """
            SELECT DISTINCT project_uuid
            FROM projects_nodes
            ORDER BY project_uuid
        """
        )
    )

    errors: list[str] = []
    restored_projects_count = 0

    for (project_uuid,) in projects_with_nodes:
        # Fetch all nodes for this project
        nodes_result = connection.execute(
            sa.text(
                """
                SELECT node_id, key, version, label, progress, thumbnail,
                       input_access, input_nodes, inputs, inputs_required, inputs_units,
                       output_nodes, outputs, run_hash, state, parent, boot_options
                FROM projects_nodes
                WHERE project_uuid = :project_uuid
                ORDER BY node_id
            """
            ),
            {"project_uuid": project_uuid},
        )

        # Fetch UI data to restore position
        ui_result = connection.execute(
            sa.text("SELECT ui FROM projects WHERE uuid = :project_uuid"),
            {"project_uuid": project_uuid},
        ).fetchone()
        ui_data: dict[str, Any] = {}
        if ui_result and ui_result[0]:
            try:
                ui_data = ui_result[0] if isinstance(ui_result[0], dict) else json.loads(ui_result[0])
            except (json.JSONDecodeError, TypeError):
                pass
        workbench_ui: dict[str, Any] = ui_data.get("workbench", {}) if isinstance(ui_data, dict) else {}

        workbench_data: dict[str, Any] = {}

        for row in nodes_result:
            node_id = row.node_id

            # Build node data dictionary
            node_data: dict[str, Any] = {
                "key": row.key,
                "version": row.version,
                "label": row.label,
            }

            # Add optional fields if they exist
            if row.progress is not None:
                node_data["progress"] = float(row.progress)
            if row.thumbnail:
                node_data["thumbnail"] = row.thumbnail
            if row.input_access:
                node_data["inputAccess"] = row.input_access
            if row.input_nodes:
                node_data["inputNodes"] = row.input_nodes
            if row.inputs:
                node_data["inputs"] = row.inputs
            if row.inputs_required:
                node_data["inputsRequired"] = row.inputs_required
            if row.inputs_units:
                node_data["inputsUnits"] = row.inputs_units
            if row.output_nodes:
                node_data["outputNodes"] = row.output_nodes
            if row.outputs:
                node_data["outputs"] = row.outputs
            if row.run_hash:
                node_data["runHash"] = row.run_hash
            if row.state:
                node_data["state"] = row.state
            if row.parent:
                node_data["parent"] = row.parent
            if row.boot_options:
                node_data["bootOptions"] = row.boot_options

            # Restore position from projects.ui
            node_ui = workbench_ui.get(node_id, {})
            if isinstance(node_ui, dict) and "position" in node_ui:
                node_data["position"] = node_ui["position"]

            workbench_data[node_id] = node_data

        if workbench_data:
            try:
                # Update the project with the restored workbench data
                connection.execute(
                    sa.text(
                        """
                        UPDATE projects
                        SET workbench = :workbench_data
                        WHERE uuid = :project_uuid
                    """
                    ),
                    {
                        "project_uuid": project_uuid,
                        "workbench_data": json.dumps(workbench_data),
                    },
                )
                restored_projects_count += 1

            except Exception as e:
                errors.append(f"Project {project_uuid}: Failed to restore workbench data - {e}")

    _logger.info("Downgrade summary: %d projects restored with workbench data", restored_projects_count)

    if errors:
        error_message = f"Downgrade failed with {len(errors)} errors:\n" + "\n".join(errors)
        _logger.error(error_message)
        raise RuntimeError(error_message)


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    # Migrate position data to projects.ui before dropping workbench
    _migrate_position_to_projects_ui()

    # Migrate workbench data to projects_nodes before dropping the column
    _migrate_workbench_to_projects_nodes()

    op.drop_column("projects", "workbench")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "projects",
        sa.Column(
            "workbench",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )

    # Restore workbench data from projects_nodes table
    _restore_workbench_from_projects_nodes()

    # Projects that were empty before the upgrade do not have rows in
    # projects_nodes, so restore them to the original empty workbench value
    # before re-applying the NOT NULL constraint.
    op.execute(
        sa.text(
            """
            UPDATE projects
            SET workbench = '{}'::json
            WHERE workbench IS NULL
            """
        )
    )

    # Now enforce NOT NULL after data has been restored
    op.alter_column("projects", "workbench", nullable=False)
    # ### end Alembic commands ###
