import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import expression

from ._common import RefActions
from .base import metadata

services_meta_data = sa.Table(
    #
    #   Combines properties as
    #     - service identifier: key, version
    #     - overridable properties of the service metadata defined upon publication (injected in the image labels)
    #     - extra properties assigned during its lifetime (e.g. deprecated, quality, etc)
    #
    "services_meta_data",
    metadata,
    # PRIMARY KEY ----------------------------
    sa.Column(
        "key",
        sa.String,
        nullable=False,
        doc="Hierarchical identifier of the service e.g. simcore/services/dynamic/my-super-service",
    ),
    sa.Column(
        "version",
        sa.String,
        nullable=False,
        doc="Service version. See format in ServiceVersion",
    ),
    # OWNERSHIP ----------------------------
    sa.Column(
        "owner",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_services_meta_data_gid_groups",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.RESTRICT,
        ),
        nullable=True,
        doc="Identifier of the group that owns this service (editable)",
    ),
    # DISPLAY ----------------------------
    sa.Column(
        "name",
        sa.String,
        nullable=False,
        doc="Display label (editable)",
    ),
    sa.Column(
        "description",
        sa.String,
        nullable=False,
        doc="Markdown-compatible description (editable). SEE `description_ui`",
    ),
    sa.Column(
        "description_ui",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="A flag that determines how the `description` column is rendered in the UI (editable)"
        "Specifically, it indicates whether the `description` should be presented as a single web page (=true) or in another structured format (default=false)."
        "This field is primarily used by the front-end of the application to decide on the presentation style of the service's metadata.",
    ),
    sa.Column(
        "thumbnail",
        sa.String,
        nullable=True,
        doc="Link to image to us as service thumbnail (editable)",
    ),
    sa.Column(
        "version_display",
        sa.String,
        nullable=True,
        doc="A user-friendly or version of the inner software e.g. Matterhorn 2.3 (editable)",
    ),
    # TAGGING -----------------------------
    sa.Column(
        "classifiers",
        ARRAY(sa.String, dimensions=1),
        nullable=False,
        server_default="{}",
        doc="List of standard labels that describe this service (see classifiers table) (editable) ",
    ),
    sa.Column(
        "quality",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Free JSON with quality assesment based on TSR (editable)",
    ),
    # LIFECYCLE ----------------------------
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
        doc="Timestamp on creation",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        doc="Timestamp with last update",
    ),
    sa.Column(
        "deprecated",
        sa.DateTime(),
        nullable=True,
        server_default=sa.null(),
        doc="Timestamp when the service is retired (editable)."
        "A fixed time before this date, service is marked as deprecated.",
    ),
    sa.PrimaryKeyConstraint("key", "version", name="services_meta_data_pk"),
)


services_access_rights = sa.Table(
    #
    #   Defines access rights (execute_access, write_access) on a service (key)
    #   for a given group (gid) on a product (project_name)
    #
    "services_access_rights",
    metadata,
    sa.Column(
        "key",
        sa.String,
        nullable=False,
        doc="Service Key Identifier",
    ),
    sa.Column(
        "version",
        sa.String,
        nullable=False,
        doc="Service version",
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_services_gid_groups",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        doc="Group Identifier of user that get these access-rights",
    ),
    # ACCESS RIGHTS FLAGS ---------------------------------------
    sa.Column(
        "execute_access",
        sa.Boolean,
        nullable=False,
        server_default=sa.false(),
        doc="If true, group can execute the service",
    ),
    sa.Column(
        "write_access",
        sa.Boolean,
        nullable=False,
        server_default=sa.false(),
        doc="If true, group can modify the service",
    ),
    # -----
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            name="fk_services_name_products",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        doc="Product Identifier",
    ),
    # LIFECYCLE ----------------------------
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
        doc="Timestamp of creation",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        doc="Timestamp on last update",
    ),
    sa.ForeignKeyConstraint(
        ["key", "version"],
        ["services_meta_data.key", "services_meta_data.version"],
        onupdate=RefActions.CASCADE,
        ondelete=RefActions.CASCADE,
    ),
    sa.PrimaryKeyConstraint(
        "key", "version", "gid", "product_name", name="services_access_pk"
    ),
)
