from pydantic import SecretStr


def _mask(value):
    """
    Mask the password, showing only the first and last characters
    or *** if very short passwords
    """
    if len(value) > 2:
        masked_value = value[0] + "*" * (len(value) - 2) + value[-1]
    else:
        # In case of very short passwords
        masked_value = "*" * len(value)
    return masked_value


def _hash(value):
    """Uses hash number to mask the password"""
    return f"hash:{hash(value)}"


class Secret4TestsStr(SecretStr):
    """Prints a hint of the secret
    TIP: Can be handy for testing
    """

    def _display(self) -> str | bytes:
        # SEE overrides _SecretBase._display
        value = self.get_secret_value()
        return _mask(value) if value else ""


assert str(Secret4TestsStr("123456890")) == "1*******0"
assert "1*******0" in repr(Secret4TestsStr("123456890"))
