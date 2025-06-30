"""Security subsystem.

- Responsible of authentication and authorization


See login/decorators.py
Based on https://aiohttp-security.readthedocs.io/en/latest/
"""

import logging

import aiohttp_security  # type: ignore[import-untyped]
from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..db.plugin import setup_db
from ..session.plugin import setup_session
from ._authz_access_model import RoleBasedAccessModel
from ._authz_access_roles import ROLES_PERMISSIONS
from ._authz_policy import AuthorizationPolicy
from ._identity_policy import SessionIdentityPolicy

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.SYSTEM, settings_name="WEBSERVER_SECURITY", logger=_logger
)
def setup_security(app: web.Application):
    # NOTE: No need to add a dependency with products domain, i.e. do not call setup_products.
    #       The logic about the product is obtained via the security repository
    setup_session(app)
    setup_db(app)

    # Identity Policy: uses sessions to identify (SEE how sessions are setup in session/plugin.py)
    identity_policy = SessionIdentityPolicy()

    # Authorization Policy: role-based access model
    role_based_access_model = RoleBasedAccessModel.from_rawdata(ROLES_PERMISSIONS)
    authorization_policy = AuthorizationPolicy(
        app, access_model=role_based_access_model
    )
    aiohttp_security.setup(app, identity_policy, authorization_policy)
