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
        server_default="o²S²PARC",
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
        server_default="@".join(["support", "osparc." + "io"]),
        doc="Support email for this product"
        'Therefore smtp_sender = f"{display_name} support <{support_email}>"',
    ),
    sa.Column(
        "twilio_messaging_sid",
        sa.String,
        nullable=True,
        doc="String Identifier (SID) to a phone from which SMS are sent for this product."
        "The SID of the Messaging Service you want to associate with the message."
        "When set to None, this feature is disabled.",
    ),
    sa.Column(
        "manual_url",
        sa.String,
        nullable=False,
        server_default="https://itisfoundation.github.io/osparc-manual/",
        doc="URL to main product's manual",
    ),
    sa.Column(
        "manual_extra_url",
        sa.String,
        nullable=True,
        server_default="https://itisfoundation.github.io/osparc-manual-z43/",
        doc="URL to extra product's manual",
    ),
    sa.Column(
        "issues_login_url",
        sa.String,
        nullable=False,
        server_default="https://github.com/ITISFoundation/osparc-simcore/issues",
        doc="URL to login in the issue tracker site",
    ),
    sa.Column(
        "issues_new_url",
        sa.String,
        nullable=False,
        server_default="https://github.com/ITISFoundation/osparc-simcore/issues/new",
        doc="URL to create a new issue for this product (e.g. fogbugz new case, github new issues)",
    ),
    sa.Column(
        "feedback_form_url",
        sa.String,
        nullable=True,
        doc="URL to a feedback form (e.g. google forms etc)",
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
