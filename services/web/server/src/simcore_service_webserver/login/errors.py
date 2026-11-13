from ..errors import WebServerBaseError


class LoginError(WebServerBaseError, ValueError): ...


class SendingVerificationSmsError(LoginError):
    msg_template = "Sending verification sms failed: {details}"


class SendingVerificationEmailError(LoginError):
    msg_template = "Sending verification email failed: {details}"


class WrongPasswordError(LoginError):
    msg_template = "Invalid password provided for user {user_id}"


class WeakPasswordError(LoginError):
    msg_template = "Password shorter than the minimum length of {LOGIN_PASSWORD_MIN_LENGTH} characters"
