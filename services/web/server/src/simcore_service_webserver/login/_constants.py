from typing import Final

from common_library.user_messages import user_message

MSG_2FA_CODE_SENT: Final[str] = user_message(
    "A code was sent by SMS to {phone_number}."
)
MSG_2FA_UNAVAILABLE: Final[str] = user_message(
    "Two-factor authentication is temporarily unavailable"
)
MSG_ACTIVATED: Final[str] = user_message("Your account has been activated.")
MSG_ACTIVATION_REQUIRED: Final[str] = user_message(
    "Please activate your account via the email we sent before logging in."
)
MSG_AUTH_FAILED: Final[str] = user_message(
    "Authorization was not successful. Please check your credentials and try again."
)
MSG_CANT_SEND_MAIL: Final[str] = user_message(
    "Unable to send email at this time. Please try again later."
)
MSG_CHANGE_EMAIL_REQUESTED: Final[str] = user_message(
    "Please click the verification link sent to your new email address."
)
MSG_EMAIL_CHANGED: Final[str] = user_message("Your email address has been updated.")
MSG_EMAIL_ALREADY_REGISTERED: Final[str] = user_message(
    "This email address is already registered. Try logging in or use a different address."
)
MSG_EMAIL_SENT: Final[str] = user_message(
    "An email was sent to {email} with further instructions."
)
MSG_LOGGED_IN: Final[str] = user_message("You have successfully logged in.")
MSG_LOGGED_OUT: Final[str] = user_message("You have successfully logged out.")
MSG_OFTEN_RESET_PASSWORD: Final[str] = user_message(
    "You've requested a password reset recently. Please use the link we sent you or wait before requesting again."
)
MSG_PASSWORD_CHANGE_NOT_ALLOWED: Final[str] = user_message(
    "Unable to reset password. Permissions may have expired or been removed. "
    "Please try again, or contact support if the problem continues: {support_email}"
)
MSG_PASSWORD_CHANGED: Final[str] = user_message("Your password has been updated.")
MSG_PASSWORD_MISMATCH: Final[str] = user_message(
    "Password and confirmation do not match. Please try again."
)
MSG_PHONE_MISSING: Final[str] = user_message(
    "No phone number is associated with this account."
)
MSG_UNAUTHORIZED_CODE_RESEND_2FA: Final[str] = user_message(
    "You can no longer resend the code. Please restart the verification process."
)
MSG_UNAUTHORIZED_LOGIN_2FA: Final[str] = user_message(
    "You can no longer submit a code. Please restart the login process."
)
MSG_UNAUTHORIZED_REGISTER_PHONE: Final[str] = user_message(
    "Phone registration is no longer allowed. Please restart the registration process."
)
MSG_UNAUTHORIZED_PHONE_CONFIRMATION: Final[str] = user_message(
    "You can no longer submit a code. Please restart the confirmation process."
)
MSG_UNKNOWN_EMAIL: Final[str] = user_message("This email address is not registered.")
MSG_USER_DELETED: Final[str] = user_message(
    "This account is scheduled for deletion. To reactivate it or for more information, please contact support: {support_email}"
)
MSG_USER_BANNED: Final[str] = user_message(
    "Access to this account is no longer available. Please contact support for more information: {support_email}"
)
MSG_USER_EXPIRED: Final[str] = user_message(
    "This account has expired and access is no longer available. Please contact support for assistance: {support_email}"
)
MSG_USER_DISABLED: Final[str] = user_message(
    "This account has been disabled and cannot be registered again. Please contact support for details: {support_email}"
)
MSG_WRONG_2FA_CODE__INVALID: Final[str] = user_message(
    "The code entered is not valid. Please enter a valid code or generate a new one."
)
MSG_WRONG_2FA_CODE__EXPIRED: Final[str] = user_message(
    "The code has expired. Please generate a new code."
)
MSG_WRONG_CAPTCHA__INVALID: Final[str] = user_message(
    "The CAPTCHA entered is incorrect. Please try again."
)
MSG_WRONG_PASSWORD: Final[str] = user_message(
    "The password is incorrect. Please try again."
)
MSG_WEAK_PASSWORD: Final[str] = user_message(
    "Password must be at least {LOGIN_PASSWORD_MIN_LENGTH} characters long."
)
MSG_INVITATIONS_CONTACT_SUFFIX: Final[str] = user_message(
    "Please contact our support team to request a new invitation."
)

# Login Accepted Response Codes:
#  - These string codes are used to identify next step in the login (e.g. login_2fa or register_phone?)
#  - The frontend uses them also to determine what page/form has to display to the user for next step
CODE_PHONE_NUMBER_REQUIRED: Final[str] = "PHONE_NUMBER_REQUIRED"
CODE_2FA_SMS_CODE_REQUIRED: Final[str] = "SMS_CODE_REQUIRED"
CODE_2FA_EMAIL_CODE_REQUIRED: Final[str] = "EMAIL_CODE_REQUIRED"


# App keys for login plugin
# Naming convention: APP_LOGIN_...KEY
APP_LOGIN_SETTINGS_PER_PRODUCT_KEY: Final[str] = (
    f"{__name__}.LOGIN_SETTINGS_PER_PRODUCT"
)


# maximum amount the user can resend the code via email or phone
MAX_2FA_CODE_RESEND: Final[int] = 5

# maximum number of trials to validate the passcode
MAX_2FA_CODE_TRIALS: Final[int] = 5

CAPTCHA_SESSION_KEY: Final[str] = "captcha"
