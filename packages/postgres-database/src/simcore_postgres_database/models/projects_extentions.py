import sqlalchemy as sa

from ._common import RefActions
from .base import metadata
from .projects import projects

projects_extentions = sa.Table(
    "projects_extentions",
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            name="fk_projects_extentions_project_uuid_projects",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        primary_key=True,
        doc="project reference and primary key for this table",
    ),
    sa.Column(
        "allow_guests_to_push_states_and_output_ports",
        sa.Boolean(),
        nullable=False,
        server_default=sa.sql.expression.false(),
        doc=(
            "When True, guest will save the state of a service "
            "and also push the data to the output ports"
        ),
    ),
)
