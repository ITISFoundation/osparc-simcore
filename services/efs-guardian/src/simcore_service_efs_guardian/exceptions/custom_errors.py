from ._base import EfsGuardianBaseError


class CustomBaseError(EfsGuardianBaseError):
    pass


class ApplicationSetupError(CustomBaseError):
    pass
