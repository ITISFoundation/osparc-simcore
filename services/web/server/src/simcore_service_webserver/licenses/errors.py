from ..errors import WebServerBaseError


class LicensesValueError(WebServerBaseError, ValueError):
    ...


class LicenseGoodNotFoundError(LicensesValueError):
    msg_template = "License good {license_good_id} not found"
