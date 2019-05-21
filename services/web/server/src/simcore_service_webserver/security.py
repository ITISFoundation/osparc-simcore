""" Security subsystem.

    - Responsible of authentication and authorization


    See login/decorators.py
    Based on https://aiohttp-security.readthedocs.io/en/latest/
"""
# pylint: disable=assignment-from-no-return
import logging

import aiohttp_security
from aiohttp_security.session_identity import SessionIdentityPolicy

from .security_access_model import RoleBasedAccessModel
from .security_authorization import AuthorizationPolicy
from .security_roles import ROLES_PERMISSIONS

log = logging.getLogger(__file__)


def setup(app):
    log.debug("Setting up %s ...", __name__)

    # Once user is identified, an identity string is created for that user
    identity_policy = SessionIdentityPolicy()

    # TODO: limitations is that it cannot contain checks need to be added here
    access_model = RoleBasedAccessModel.from_rawdata(ROLES_PERMISSIONS)

    # TODO: create basic/bearer authentication policy based on tokens instead of cookies!!
    authorization_policy = AuthorizationPolicy(app, access_model)
    aiohttp_security.setup(app, identity_policy, authorization_policy)

setup_security = setup

__all__ = (
    'setup_security'
)
