"""Remove workbench column from projects_table

Revision ID: 201aa37f4d9a
Revises: 5679165336c8
Create Date: 2025-07-22 19:25:42.125196+00:00

"""

import json
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "201aa37f4d9a"
down_revision = "5679165336c8"
branch_labels = None
depends_on = None


def _migrate_workbench_to_projects_nodes() -> None:
    """Migrate nodes from projects.workbench to projects_nodes table."""

    # Get database connection
    connection = op.get_bind()

    # Fetch all projects with workbench data
    projects_result = connection.execute(
        sa.text("SELECT uuid, workbench FROM projects WHERE workbench IS NOT NULL")
    )

    errors: list[str] = []
    updated_nodes_count = 0
    inserted_nodes_count = 0

    for project_uuid, workbench_json in projects_result:
        if not workbench_json:
            continue

        try:
            workbench_data = (
                workbench_json
                if isinstance(workbench_json, dict)
                else json.loads(workbench_json)
            )
        except (json.JSONDecodeError, TypeError) as e:
            errors.append(f"Project {project_uuid}: Invalid workbench JSON - {e}")
            continue

        if not isinstance(workbench_data, dict):
            errors.append(f"Project {project_uuid}: Workbench is not a dictionary")
            continue

        for node_id, node_data in workbench_data.items():
            if not isinstance(node_data, dict):
                errors.append(
                    f"Project {project_uuid}, Node {node_id}: Node data is not a dictionary"
                )
                continue

            # Validate required fields
            missing_fields = []
            if not node_data.get("key"):
                missing_fields.append("key")
            if not node_data.get("version"):
                missing_fields.append("version")
            if not node_data.get("label"):
                missing_fields.append("label")

            if missing_fields:
                errors.append(
                    f"Project {project_uuid}, Node {node_id}: Missing required fields: {', '.join(missing_fields)}"
                )
                continue

            # Check if node already exists
            existing_node = connection.execute(
                sa.text(
                    "SELECT project_node_id FROM projects_nodes WHERE project_uuid = :project_uuid AND node_id = :node_id"
                ),
                {"project_uuid": project_uuid, "node_id": node_id},
            ).fetchone()

            # Prepare node data for insertion/update
            node_values = {
                "project_uuid": project_uuid,
                "node_id": node_id,
                "key": node_data["key"],
                "version": node_data["version"],
                "label": node_data["label"],
                "progress": node_data.get("progress"),
                "thumbnail": node_data.get("thumbnail"),
                "input_access": (
                    json.dumps(node_data["input_access"])
                    if node_data.get("input_access")
                    else None
                ),
                "input_nodes": (
                    json.dumps(node_data["input_nodes"])
                    if node_data.get("input_nodes")
                    else None
                ),
                "inputs": (
                    json.dumps(node_data["inputs"]) if node_data.get("inputs") else None
                ),
                "inputs_required": (
                    json.dumps(node_data["inputs_required"])
                    if node_data.get("inputs_required")
                    else None
                ),
                "inputs_units": (
                    json.dumps(node_data["inputs_units"])
                    if node_data.get("inputs_units")
                    else None
                ),
                "output_nodes": (
                    json.dumps(node_data["output_nodes"])
                    if node_data.get("output_nodes")
                    else None
                ),
                "outputs": (
                    json.dumps(node_data["outputs"])
                    if node_data.get("outputs")
                    else None
                ),
                "run_hash": node_data.get(
                    "run_hash", node_data.get("runHash")
                ),  # Handle both camelCase and snake_case
                "state": (
                    json.dumps(node_data["state"]) if node_data.get("state") else None
                ),
                "parent": node_data.get("parent"),
                "boot_options": (
                    json.dumps(node_data["boot_options"])
                    if node_data.get("boot_options", node_data.get("bootOptions"))
                    else None
                ),
            }

            if existing_node:
                # Update existing node
                update_sql = """
                    UPDATE projects_nodes SET
                        key = :key,
                        version = :version,
                        label = :label,
                        progress = :progress,
                        thumbnail = :thumbnail,
                        input_access = :input_access::jsonb,
                        input_nodes = :input_nodes::jsonb,
                        inputs = :inputs::jsonb,
                        inputs_required = :inputs_required::jsonb,
                        inputs_units = :inputs_units::jsonb,
                        output_nodes = :output_nodes::jsonb,
                        outputs = :outputs::jsonb,
                        run_hash = :run_hash,
                        state = :state::jsonb,
                        parent = :parent,
                        boot_options = :boot_options::jsonb,
                        modified_datetime = NOW()
                    WHERE project_uuid = :project_uuid AND node_id = :node_id
                """
                connection.execute(sa.text(update_sql), node_values)
                updated_nodes_count += 1
                print(f"Updated existing node {node_id} in project {project_uuid}")

            else:
                # Insert new node
                insert_sql = """
                    INSERT INTO projects_nodes (
                        project_uuid, node_id, key, version, label, progress, thumbnail,
                        input_access, input_nodes, inputs, inputs_required, inputs_units,
                        output_nodes, outputs, run_hash, state, parent, boot_options,
                        required_resources, created_datetime, modified_datetime
                    ) VALUES (
                        :project_uuid, :node_id, :key, :version, :label, :progress, :thumbnail,
                        :input_access::jsonb, :input_nodes::jsonb, :inputs::jsonb,
                        :inputs_required::jsonb, :inputs_units::jsonb, :output_nodes::jsonb,
                        :outputs::jsonb, :run_hash, :state::jsonb, :parent, :boot_options::jsonb,
                        '{}'::jsonb, NOW(), NOW()
                    )
                """
                connection.execute(sa.text(insert_sql), node_values)
                inserted_nodes_count += 1

    print(
        f"Migration summary: {inserted_nodes_count} nodes inserted, {updated_nodes_count} nodes updated"
    )

    if errors:
        error_message = f"Migration failed with {len(errors)} errors:\n" + "\n".join(
            errors
        )
        print(error_message)
        raise RuntimeError(error_message)


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
                errors.append(
                    f"Project {project_uuid}: Failed to restore workbench data - {e}"
                )

    print(
        f"Downgrade summary: {restored_projects_count} projects restored with workbench data"
    )

    if errors:
        error_message = f"Downgrade failed with {len(errors)} errors:\n" + "\n".join(
            errors
        )
        print(error_message)
        raise RuntimeError(error_message)


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

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
            nullable=False,
        ),
    )

    # Restore workbench data from projects_nodes table
    _restore_workbench_from_projects_nodes()
    # ### end Alembic commands ###
