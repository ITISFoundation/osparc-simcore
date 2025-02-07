from common_library.errors_classes import OsparcErrorMixin


class LicensesBaseError(OsparcErrorMixin, Exception):
    ...


class NotEnoughAvailableSeatsError(LicensesBaseError):
    msg_template = "Not enough available seats. Current available seats {available_num_of_seats} for license item {license_item_id}"


class CanNotCheckoutNotEnoughAvailableSeatsError(LicensesBaseError):
    msg_template = "Can not checkout license item {license_id} with num of seats {num_of_seats}. Currently available seats {available_num_of_seats}"


class CanNotCheckoutServiceIsNotRunningError(LicensesBaseError):
    msg_template = "Can not checkout license item {license_id} as dynamic service is not running. Current service {service_run}"


class LicenseCheckoutNotFoundError(LicensesBaseError):
    msg_template = "Licensed item checkout {license_checkout_id} not found."


LICENSES_ERRORS = (
    NotEnoughAvailableSeatsError,
    CanNotCheckoutNotEnoughAvailableSeatsError,
    CanNotCheckoutServiceIsNotRunningError,
    LicenseCheckoutNotFoundError,
)


### Transaction Error


class WalletTransactionError(OsparcErrorMixin, Exception):
    msg_template = "{msg}"
