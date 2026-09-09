from common_library.errors_classes import OsparcErrorMixin


class NotificationsRuntimeError(OsparcErrorMixin, RuntimeError): ...


class NotificationsSmsDeliveryError(NotificationsRuntimeError):
    msg_template = "Failed to send sms to {masked_phone_number}."
