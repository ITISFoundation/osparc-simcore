""" Permissions

    - Describe actions on resources using normalized labels. These are later used to determine whether a given user is allowed or not to execute it.
    - Labels convention: dot-separated labels denoting a hierarchical resource name and an action
        e.g. project.template.read => resource='template projects' and action='read'
"""
import operator
from typing import List, Tuple

from .security_roles import ROLES_PERMISSIONS


def named_permissions() -> List[str]:
    """ Lists available named permissions
    """
    permissions = []
    for role in ROLES_PERMISSIONS:
        permissions += ROLES_PERMISSIONS[role].get("can", list())
    return permissions


def split_permission_name(permission: str) -> Tuple[str, str]:
    parts = permission.split(".")
    resource, action = ".".join(parts[:-1]), parts[-1]
    return (resource, action)


def and_(lhs, rhs):
    """ And operator to create boolean expressions with permissions

        Usage:
            permission = or_(and_("project.read", "project.write"), "project.everything")
    """
    return (operator.and_, lhs, rhs)


def or_(lhs, rhs):
    """ Or operator to create boolean expressions with permissions

        Usage:
            permission = or_(and_("project.read", "project.write"), "project.everything")
    """
    return (operator.or_, lhs, rhs)
