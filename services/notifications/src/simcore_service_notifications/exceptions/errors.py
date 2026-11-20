from common_library.errors_classes import OsparcErrorMixin


class NotificationsRuntimeError(OsparcErrorMixin, RuntimeError): ...


class InvalidNotificationsChannelSettingsError(NotificationsRuntimeError):
    msg_template = "Invalid {env_name}: {errors}. Field values are not echoed to avoid leaking credentials"


class NotificationsSmsDeliveryError(NotificationsRuntimeError):
    msg_template = "Failed to send sms to {masked_phone_number}."


class NotificationsSmsDeliveryPermanentError(NotificationsSmsDeliveryError):
    """the provider rejected the message for a reason a retry will not fix"""

    msg_template = "Failed to send sms to {masked_phone_number}: permanent rejection."
