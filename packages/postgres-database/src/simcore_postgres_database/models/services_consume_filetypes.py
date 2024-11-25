"""
    Establishes which services can consume a given filetype

    The relation is N-N because
    - a service could handle one or more filetypes and
    - one filetype could be handled by one or more services
"""
import sqlalchemy as sa

from ._common import RefActions
from .base import metadata

#
# TODO: This information SHALL be defined in service metadata upon publication
#       and the catalog service, using e.g. a background task,
#       can automatically fill this table with services that elligable (e.g. shared with everybody)
#       to consume given filetypes. Notice also that service "matching" will also be determined in a near
#       future by more complex metadata
#

services_consume_filetypes = sa.Table(
    "services_consume_filetypes",
    metadata,
    sa.Column(
        "service_key",
        sa.String,
        nullable=False,
        doc="Key part of a $key:$version service resource name",
    ),
    sa.Column(
        "service_version",
        sa.String,
        nullable=False,
        doc="Defines the minimum version (included) of this version from which this information applies",
    ),
    sa.Column(
        "service_display_name",
        sa.String,
        nullable=False,
        doc="Human readable name to display",
    ),
    sa.Column(
        "service_input_port",
        sa.String,
        nullable=False,
        doc="Key name of the service input that consumes this filetype",
    ),
    sa.Column(
        "filetype",
        sa.String,
        sa.CheckConstraint(
            "filetype = upper(filetype)",
            name="ck_filetype_is_upper",
        ),
        nullable=False,
        doc="An extension supported by this service, e.g. CSV, VTK, etc."
        "The filetype identifiers are not well defined, so we avoided using enums"
        "Temptative list in https://en.wikipedia.org/wiki/List_of_file_formats",
    ),
    sa.Column(
        "preference_order",
        sa.SmallInteger,
        nullable=True,
        doc="Index used as discriminator to sort services handling the same filetype."
        "The default service to consume this filetime is the one with lowest preference_order value",
    ),
    sa.Column(
        "is_guest_allowed",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
        doc="If set to True, then the viewer is also available for guest users."
        "Otherwise only registered users can dispatch it.",
    ),
    # If service-key/version gets deleted from service_metadata, it should be deleted from here
    sa.ForeignKeyConstraint(
        ["service_key", "service_version"],
        ["services_meta_data.key", "services_meta_data.version"],
        onupdate=RefActions.CASCADE,
        ondelete=RefActions.CASCADE,
    ),
    # This table stores services (key:version) that consume filetype by AT LEAST one input_port
    # if more ports can consume, then it should only be added once in this table
    sa.PrimaryKeyConstraint(
        "service_key",
        "service_version",
        "filetype",
        name="services_consume_filetypes_pk",
    ),
)
