from ..errors import WebServerBaseError


class LicensesValueError(WebServerBaseError, ValueError):
    ...


class LicenseNotFoundError(LicensesValueError):
    msg_template = "License {license_id} not found"


class LicensedItemNotFoundError(LicensesValueError):
    msg_template = "License good {licensed_item_id} not found"


class LicensedItemPricingPlanMatchError(LicensesValueError):
    msg_template = "The provided pricing plan {pricing_plan_id} does not match the one associated with the licensed item {licensed_item_id}."
