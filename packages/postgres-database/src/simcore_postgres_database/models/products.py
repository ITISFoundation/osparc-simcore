""" Products table

    - List of products served by the simcore platform
    - Products have a name and an associated host (defined by a regex)
    - Every product has a front-end with exactly the same name
"""

import sqlalchemy as sa
from sqlalchemy.sql import func

from .base import metadata

products = sa.Table(
    "products",
    metadata,
    sa.Column(
        "name",
        sa.String,
        nullable=False,
        doc="Uniquely identifies a product",
    ),
    sa.Column(
        "display_name",
        sa.String,
        nullable=False,
        default="o²S²PARC",
        doc="Human readable name of the product or display name",
    ),
    sa.Column(
        "host_regex",
        sa.String,
        nullable=False,
        doc="Regular expression that matches product hostname from an url string",
    ),
    sa.Column(
        "support_email",
        sa.String,
        nullable=False,
        default="@".join(["support", "osparc." + "io"]),
        doc="Support email for this product"
        'Therefore smtp_sender = f"{display_name} support <{support_email}>"',
    ),
    sa.Column(
        "twilio_messaging_sid",
        sa.String,
        nullable=True,
        doc="String Identifier (SID) to a phone from which SMS are sent for this product."
        "When set to None, this feature is disabled.",
    ),
    sa.Column(
        "manual_url",
        sa.String,
        nullable=False,
        default="http://docs.osparc.io/",
        doc="URL to main product's manual",
    ),
    sa.Column(
        "manual_extra_url",
        sa.String,
        nullable=True,
        default="https://itisfoundation.github.io/osparc-manual-z43/",
        doc="URL to extra product's manual",
    ),
    sa.Column(
        "issues_new_url",
        sa.String,
        nullable=False,
        default="https://z43.manuscript.com/f/cases/new?command=new&pg=pgEditBug&ixProject=45&ixArea=458",
        doc="URL to create a new issue for this product (e.g. fogbugz new case, github new issues)",
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
    sa.PrimaryKeyConstraint("name", name="products_pk"),
)
