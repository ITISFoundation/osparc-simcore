"""
    Establishes which services can consume a given filetype

    The relation is N-N because
    - a service could handle one or more filetypes and
    - one filetype could be handled by one or more services
"""
import sqlalchemy as sa

from .base import metadata

#
# TODO: this information SHALL be defined in service metadata upon publication
# and the catalog can automatically move here
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
        doc="Version part of a $key:$version service resource name",
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
        default="input_1",
        doc="Key name of the service input that consumes this filetype",
    ),
    sa.Column(
        "filetype",
        sa.String,
        nullable=False,
        doc="A filetype supported by this service, e.g. CSV, Excel, ect."
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
    # If service-key/version gets deleted from service_metadata, it should be deleted from here
    sa.ForeignKeyConstraint(
        ["service_key", "service_version"],
        ["services_meta_data.key", "services_meta_data.version"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    ),
)
