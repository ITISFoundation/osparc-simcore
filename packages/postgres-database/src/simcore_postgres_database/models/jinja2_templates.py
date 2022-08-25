""" Collection of jinja2 templates for customizable docs (e.g. emails, sites)

"""

import sqlalchemy as sa

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
        doc="Text with jinja template. Should be parsable with jinja2",
    ),
    sa.PrimaryKeyConstraint("name", name="jinja2_templates_name_pk"),
)
