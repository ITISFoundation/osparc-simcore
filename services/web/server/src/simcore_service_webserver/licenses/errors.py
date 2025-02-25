from ..errors import WebServerBaseError


class LicensesValueError(WebServerBaseError, ValueError):
    ...


class LicensedItemNotFoundError(LicensesValueError):
    msg_template = "License item {licensed_item_id} not found"


class LicensedKeyVersionNotFoundError(LicensesValueError):
    msg_template = "License key {key} version {version} not found"


class LicensedResourceNotFoundError(LicensesValueError):
    msg_template = "License resource {licensed_resource_id} not found"


class LicensedItemPricingPlanMatchError(LicensesValueError):
    msg_template = "The provided pricing plan {pricing_plan_id} does not match the one associated with the licensed item {licensed_item_id}."


class LicnesedItemPricingPlanConfigurationError(LicensesValueError):
    msg_template = "Pricing plan {pricing_plan_id} has wrong configuration. Please contact support."


class LicnesedItemNumOfSeatsMatchError(LicensesValueError):
    msg_template = "Num of seats provided by frontend client {num_of_seats} does not match the one associated to pricing unit {pricing_unit_id}"
