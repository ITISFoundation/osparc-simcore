import base64
import pickle


class TransferrableCeleryError(Exception):
    def __repr__(self) -> str:
        exception = decode_celery_transferrable_error(self)
        return f"{self.__class__.__name__}({exception.__class__.__name__}({exception}))"

    def __str__(self) -> str:
        return f"{decode_celery_transferrable_error(self)}"


def encode_celery_transferrable_error(error: Exception) -> TransferrableCeleryError:
    # NOTE: Celery modifies exceptions during serialization, which can cause
    # the original error context to be lost. This mechanism ensures the same
    # error can be recreated on the caller side exactly as it was raised here.
    return TransferrableCeleryError(base64.b64encode(pickle.dumps(error)))


def decode_celery_transferrable_error(error: TransferrableCeleryError) -> Exception:
    assert isinstance(error, TransferrableCeleryError)  # nosec
    result: Exception = pickle.loads(base64.b64decode(error.args[0]))  # noqa: S301
    return result
