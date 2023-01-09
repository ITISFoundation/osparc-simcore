""" Products table

    - List of products served by the simcore platform
    - Products have a name and an associated host (defined by a regex)
    - Every product has a front-end with exactly the same name
"""

import json
from dataclasses import asdict, dataclass
from typing import Literal, TypedDict

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func, text

from .base import metadata
from .groups import groups
from .jinja2_templates import jinja2_templates

# NOTE: a default entry is created in the table Product
# see packages/postgres-database/src/simcore_postgres_database/migration/versions/350103a7efbd_modified_products_table.py


#
# Layout of the data in the JSONB columns
#


class Vendor(TypedDict, total=False):
    """
        Brand information about the vendor
    E.g. company name, address, copyright, etc.
    """

    name: str
    copyright: str
    url: str
    license_url: str  # Which are the license terms? (if applies)
    invitation_url: str  # How to request a trial invitation? (if applies)


class IssueTracker(TypedDict, total=True):
    """Link to actions in an online issue tracker (e.g. in fogbugz, github, gitlab ...)

    e.g. URL to create a new issue for this product

    new_url=https://github.com/ITISFoundation/osparc-simcore/issues/new/choose
    """

    label: str
    login_url: str
    new_url: str


class Manual(TypedDict, total=True):
    label: str
    url: str


class WebFeedback(TypedDict, total=True):
    """URL to a feedback form (e.g. google forms etc)"""

    kind: Literal["web"]
    label: str
    url: str


class EmailFeedback(TypedDict, total=True):
    """Give feedback via email"""

    kind: Literal["email"]
    label: str
    email: str


class Forum(TypedDict, total=True):
    """Link to a forum"""

    kind: Literal["forum"]
    label: str
    url: str


@dataclass(frozen=True)
class ProductLoginSettings:
    """Login plugin settings customized for this product

    Extends simcore_service_webserver.login.settings.LoginSettings
    """

    two_factor_enabled: bool = False


# NOTE: defaults affects migration!!
LOGIN_SETTINGS_DEFAULT = ProductLoginSettings()
_LOGIN_SETTINGS_SERVER_DEFAULT = json.dumps(asdict(LOGIN_SETTINGS_DEFAULT))


#
# Table
#
# NOTE: a default entry is created in the table Product
# see packages/postgres-database/src/simcore_postgres_database/migration/versions/350103a7efbd_modified_products_table.py

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
        "short_name",
        sa.String,
        nullable=False,
        server_default="osparc",
        doc="Alphanumeric name up to 11 characters long with characters "
        "include both upper- and lower-case Ascii letters, the digits 0 through 9, "
        "and the space character. They may not be only numerals.",
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
    sa.Column("vendor", JSONB, nullable=True, doc="Info about the Vendor"),
    sa.Column("issues", JSONB, nullable=True, doc="Issue trackers: list[IssueTracker]"),
    sa.Column(
        "manuals",
        JSONB,
        nullable=True,
        doc="User manuals: list[Manual]",
    ),
    sa.Column(
        "support",
        JSONB,
        nullable=True,
        doc="User support: list[Forum | EmailFeedback | WebFeedback ]",
    ),
    sa.Column(
        "login_settings",
        JSONB,
        nullable=False,
        server_default=text(f"'{_LOGIN_SETTINGS_SERVER_DEFAULT}'::jsonb"),
        doc="Overrides values of simcore_service_webserver.login.settings.LoginSettings",
    ),
    sa.Column(
        "registration_email_template",
        sa.String,
        sa.ForeignKey(
            jinja2_templates.c.name,
            name="fk_jinja2_templates_name",
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        nullable=True,
        doc="Custom jinja2 template for registration email",
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
    sa.Column(
        "priority",
        sa.Integer(),
        server_default=sa.text("0"),
        doc="Index used to sort the products. E.g. determine default",
    ),
    sa.Column(
        "max_open_studies_per_user",
        sa.Integer(),
        nullable=True,
        doc="Limits the number of studies a user may have open concurently (disabled if NULL)",
    ),
    sa.Column(
        "group_id",
        sa.BigInteger,
        sa.ForeignKey(
            groups.c.gid,
            name="fk_products_group_id",
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        unique=True,
        nullable=True,
        doc="Group associated to this product",
    ),
    sa.PrimaryKeyConstraint("name", name="products_pk"),
)
