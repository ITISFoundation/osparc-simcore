"""Collection of jinja2 templates for customizable docs (e.g. emails, sites)"""

import sqlalchemy as sa
from sqlalchemy.sql import func

from .base import metadata

jinja2_templates = sa.Table(
    "jinja2_templates",
    metadata,
    sa.Column(
        "name",
        sa.String,
        nullable=False,
        doc="Uniquely identifies a template",
    ),
    sa.Column(
        "content",
        sa.Text,
        nullable=False,
        doc="Text of template. Should be parsable with jinja2",
    ),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp auto-generated upon creation",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Automaticaly updates on modification of the row",
    ),
    sa.PrimaryKeyConstraint("name", name="jinja2_templates_name_pk"),
)
