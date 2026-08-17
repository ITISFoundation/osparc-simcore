from common_library.errors_classes import OsparcErrorMixin


class KMSRuntimeError(OsparcErrorMixin, RuntimeError):
    msg_template: str = "KMS client unexpected error"


class KMSNotConnectedError(KMSRuntimeError):
    msg_template: str = "Cannot connect with KMS server"


class KMSAccessError(KMSRuntimeError):
    msg_template: str = "Unexpected error while accessing KMS backend: {operation_name}:{code}:{error}"


class KMSKeyNotFoundError(KMSAccessError):
    msg_template: str = "KMS key not found: {key_id}"


class KMSInvalidCiphertextError(KMSAccessError):
    msg_template: str = "Provided ciphertext could not be decrypted (wrong key or corrupted/tampered data)"
