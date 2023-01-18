from typing import Final

MSG_2FA_CODE_SENT: Final[str] = "Code sent by SMS to {phone_number}"
MSG_ACTIVATED: Final[str] = "Your account is activated"
MSG_ACTIVATION_REQUIRED: Final[
    str
] = "You have to activate your account via email, before you can login"
MSG_AUTH_FAILED: Final[str] = "Authorization failed"
MSG_CANT_SEND_MAIL: Final[str] = "Can't send email, try a little later"
MSG_CHANGE_EMAIL_REQUESTED: Final[
    str
] = "Please, click on the verification link we sent to your new email address"
MSG_EMAIL_CHANGED: Final[str] = "Your email is changed"
MSG_EMAIL_EXISTS: Final[str] = "This email is already registered"
MSG_EMAIL_SENT: Final[
    str
] = "An email has been sent to {email} with further instructions"
MSG_LOGGED_IN: Final[str] = "You are logged in"
MSG_LOGGED_OUT: Final[str] = "You are logged out"
MSG_OFTEN_RESET_PASSWORD: Final[str] = (
    "You can not request of restoring your password so often. Please, use"
    " the link we sent you recently"
)
MSG_PASSWORD_CHANGE_NOT_ALLOWED: Final[str] = (
    "Cannot reset password: permissions were expired or were removed"
    "Please retry and if the problem persist contact {support_email}"
)
MSG_PASSWORD_CHANGED: Final[str] = "Your password is changed"
MSG_PASSWORD_MISMATCH: Final[str] = "Password and confirmation do not match"
MSG_PHONE_MISSING: Final[str] = "No phone was registered for this user"
MSG_UNAUTHORIZED_CODE_RESEND_2FA: Final[
    str
] = "Unauthorized: you cannot resend 2FA code anymore, please restart."
MSG_UNAUTHORIZED_LOGIN_2FA: Final[
    str
] = "Unauthorized: you cannot submit the code anymore, please restart."
MSG_UNAUTHORIZED_REGISTER_PHONE: Final[
    str
] = "Unauthorized: you cannot register the phone anymore, please restart."
MSG_UNAUTHORIZED_PHONE_CONFIRMATION: Final[
    str
] = "Unauthorized: you cannot submit the code anymore, please restart."
MSG_UNKNOWN_EMAIL: Final[str] = "This email is not registered"
MSG_USER_BANNED: Final[
    str
] = "This user does not have anymore access. Please contact support for further details: {support_email}"
MSG_USER_EXPIRED: Final[
    str
] = "This account has expired and does not have anymore access. Please contact support for further details: {support_email}"
MSG_WRONG_2FA_CODE: Final[str] = "Invalid code (wrong or expired)"
MSG_WRONG_PASSWORD: Final[str] = "Wrong password"


# Login Accepted Response Codes:
#  - These string codes are used to identify next step in the login (e.g. login_2fa or register_phone?)
#  - The frontend uses them alwo to determine what page/form has to display to the user for next step
CODE_PHONE_NUMBER_REQUIRED = "PHONE_NUMBER_REQUIRED"
CODE_2FA_CODE_REQUIRED = "SMS_CODE_REQUIRED"


# App keys for login plugin
# Naming convention: APP_LOGIN_...KEY
APP_LOGIN_SETTINGS_PER_PRODUCT_KEY = f"{__name__}.LOGIN_SETTINGS_PER_PRODUCT"


#
MAX_RESEND_CODE = 5
MAX_CODE_TRIALS = MAX_RESEND_CODE + 1
