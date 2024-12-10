from ..errors import WebServerBaseError


class LicensesValueError(WebServerBaseError, ValueError):
    ...


class LicensedItemNotFoundError(LicensesValueError):
    msg_template = "License good {licensed_item_id} not found"
