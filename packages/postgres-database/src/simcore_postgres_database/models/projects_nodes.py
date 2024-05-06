""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .projects import projects

projects_nodes = sa.Table(
    "projects_nodes",
    metadata,
    sa.Column(
        "project_node_id",
        sa.Integer,
        nullable=False,
        autoincrement=True,
        primary_key=True,
        doc="Project node index",
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_projects_to_projects_nodes_to_projects_uuid",
        ),
        nullable=False,
        index=True,
        doc="The project unique identifier",
    ),
    sa.Column(
        "node_id",
        sa.String,
        nullable=False,
        index=True,
        doc="The node unique identifier",
    ),
    sa.Column(
        "required_resources",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="The node required resources",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.UniqueConstraint("project_uuid", "node_id"),
    # Previously workbench fields https://github.com/ITISFoundation/osparc-simcore/blob/e9d1386048cf394728b6fb0f2ea945677bce4e77/services/director/src/simcore_service_director/api/v0/schemas/project-v0.0.1.json
    sa.Column(
        "key",
        sa.String,
        nullable=False,
        doc="distinctive name for the node based on the docker registry path",
    ),
    sa.Column(
        "version",
        sa.String,
        nullable=False,
        doc="semantic version number of the node",
    ),
    sa.Column(
        "label",
        sa.String,
        nullable=False,
        doc="The short name of the node",
    ),
    sa.Column(
        "progress",
        sa.NUMERIC,
        nullable=False,
        doc="the node progress value",
    ),
    sa.Column(
        "thumbnail",
        sa.String,
        nullable=False,
        doc="url of the latest screenshot of the node",
    ),
    sa.Column(
        "run_hash",
        sa.String,
        nullable=True,
        doc="the hex digest of the resolved inputs + outputs hash at the time when the last outputs were generated",
    ),
    sa.Column(
        "inputs",
        JSONB,
        nullable=False,
        doc="values of input properties",
    ),
    sa.Column(
        "inputs_units",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="values of input unit",
    ),
    sa.Column(
        "input_access",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="map with key - access level pairs",
    ),
    sa.Column(
        "input_nodes",
        JSONB,  # <-- ARRAY
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
        doc="node IDs of where the node is connected to",
    ),
    sa.Column(
        "outputs",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="...",
    ),
    sa.Column(
        "output_node",
        sa.BOOLEAN,
        nullable=False,
        doc="Deprecated!",
    ),
    sa.Column(
        "output_nodes",
        JSONB,  # <-- ARRAY
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
        doc="Used in group-nodes. Node IDs of those connected to the output",
    ),
    sa.Column(
        "parent",
        sa.String,
        nullable=True,
        doc="Parent's (group-nodes') node ID s.",
    ),
    sa.Column(
        "position",
        JSONB,
        nullable=True,
        server_default=sa.text("'{}'::jsonb"),
        doc="Deprecated!",
    ),
    sa.Column(
        "state",
        JSONB,
        nullable=True,
        server_default=sa.text("'{}'::jsonb"),
        doc="Node state",
    ),
    sa.Column(
        "boot_options",
        JSONB,
        nullable=True,
        server_default=sa.text("'{}'::jsonb"),
        doc="Some services provide alternative parameters to be injected at boot time. The user selection should be stored here, and it will overwrite the services's defaults.",
    ),
)


register_modified_datetime_auto_update_trigger(projects_nodes)


"""
select
	count(distinct project_id) as distinct_project_id,
	count(distinct node_id) as distinct_node_id,
	count(distinct key) as distinct_key,
	count(distinct label) as distinct_label,
	count(distinct version) as distinct_version,
	count(distinct thumbnail) as distinct_thumbnail,
	count(distinct inputs) as distinct_inputs,
	count(distinct inputNodes) as distinct_inputNodes,
	count(distinct inputsUnits) as distinct_inputsUnits,
	count(distinct inputAccess) as distinct_inputAccess,
	count(distinct outputs) as distinct_outputs,
	count(distinct outputNode) as distinct_outputNode,
	count(distinct outputNodes) as distinct_outputNodes,
	count(distinct parent) as distinct_parent,
	count(distinct position) as distinct_position,
	count(distinct state) as distinct_state,
	count(distinct progress) as distinct_progress,
	count(distinct runHash) as distinct_runHash,
	count(distinct bootOptions) as distinct_bootOptions

from (
SELECT projects.uuid as project_id,
	js.key as node_id,
	js.value::jsonb ->>'key' as key,
	js.value::jsonb ->>'label' as label,
	js.value::jsonb ->>'version' as version,
	js.value::jsonb ->>'thumbnail' as thumbnail,
	js.value::jsonb ->>'inputs' as inputs,
	js.value::jsonb ->>'inputNodes' as inputNodes,
	js.value::jsonb ->>'inputsUnits' as inputsUnits,
	js.value::jsonb ->>'inputAccess' as inputAccess,
	js.value::jsonb ->>'outputs' as outputs,
	js.value::jsonb ->>'outputNode' as outputNode,  -- deprecated
	js.value::jsonb ->>'outputNodes' as outputNodes,
	js.value::jsonb ->>'parent' as parent,
	js.value::jsonb ->>'position' as position,  -- deprecated
	js.value::jsonb ->>'state' as state,
	js.value::jsonb ->>'progress' as progress,
	js.value::jsonb ->>'runHash' as runHash,
	js.value::jsonb ->>'bootOptions' as bootOptions
FROM   projects,
json_each(projects.workbench) AS js
) a
"""
