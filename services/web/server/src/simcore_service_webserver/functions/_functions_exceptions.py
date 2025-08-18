from common_library.errors_classes import OsparcErrorMixin


class FunctionGroupAccessRightsNotFoundError(OsparcErrorMixin, Exception):
    msg_template = "Group '{group_id}' does not have access rights to {object_type} '{object_id}' in product '{product_name}'"
