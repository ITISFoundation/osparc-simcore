""" Products table

    - List of products served by the simcore platform
    - Products have a name and an associated host (defined by a regex)
    - Every product has a front-end with exactly the same name
"""

import json
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

from ._common import RefActions
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

    name: str  # e.g. IT'IS Foundation
    address: str  # e.g. Zeughausstrasse 43, 8004 Zurich, Switzerland
    copyright: str  # copyright message

    url: str  # vendor website
    license_url: str  # Which are the license terms? (if applies)

    invitation_url: str  # How to request a trial invitation? (if applies)
    invitation_form: bool  # If True, it takes precendence over invitation_url and asks the FE to show the form (if defined)

    release_notes_url_template: str  # a template url where `{vtag}` will be replaced, eg: "http://example.com/{vtag}.md"


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


class ProductLoginSettingsDict(TypedDict, total=False):
    """Login plugin settings customized for this product

    Overrides simcore_service_webserver.login.settings.LoginSettings
    (i.e. if not defined, the values of LoginSettings apply)

    NOTE: These attributes need to match those of LoginSettings
    """

    LOGIN_REGISTRATION_CONFIRMATION_REQUIRED: bool
    LOGIN_REGISTRATION_INVITATION_REQUIRED: bool
    LOGIN_2FA_REQUIRED: bool  # previously 'two_factor_enabled'


# NOTE: defaults affects migration!!
LOGIN_SETTINGS_DEFAULT = ProductLoginSettingsDict()  # = {}
_LOGIN_SETTINGS_SERVER_DEFAULT = json.dumps(LOGIN_SETTINGS_DEFAULT)


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
    sa.Column(
        "vendor",
        JSONB,
        nullable=True,
        doc="Info about the Vendor",
    ),
    sa.Column(
        "issues",
        JSONB,
        nullable=True,
        doc="Issue trackers: list[IssueTracker]",
    ),
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
        server_default=sa.text(f"'{_LOGIN_SETTINGS_SERVER_DEFAULT}'::jsonb"),
        doc="Overrides simcore_service_webserver.login.settings.LoginSettings."
        "SEE LoginSettingsForProduct",
    ),
    sa.Column(
        "registration_email_template",
        sa.String,
        sa.ForeignKey(
            jinja2_templates.c.name,
            name="fk_jinja2_templates_name",
            ondelete=RefActions.SET_NULL,
            onupdate=RefActions.CASCADE,
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
            ondelete=RefActions.SET_NULL,
            onupdate=RefActions.CASCADE,
        ),
        unique=True,
        nullable=True,
        doc="Group associated to this product",
    ),
    sa.PrimaryKeyConstraint("name", name="products_pk"),
)
