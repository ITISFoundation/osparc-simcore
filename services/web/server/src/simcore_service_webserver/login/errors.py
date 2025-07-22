from ..errors import WebServerBaseError


class LoginError(WebServerBaseError, ValueError): ...


class SendingVerificationSmsError(LoginError):
    msg_template = "Sending verification sms failed. {reason}"


class SendingVerificationEmailError(LoginError):
    msg_template = "Sending verification email failed. {reason}"


class WrongPasswordError(LoginError):
    msg_template = "Invalid password provided"
