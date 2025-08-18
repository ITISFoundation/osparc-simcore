from common_library.errors_classes import OsparcErrorMixin


class FunctionGroupAccessRightsNotFoundError(OsparcErrorMixin, Exception):
    msg_template = "Group access rights not found for {object_type} '{object_id}' in product '{product_name}'"
