class CaptureProcessingError(Exception):
    # base for all the exceptions in this submodule
    pass


class VerbNotInPathError(CaptureProcessingError):
    pass


class PathNotInOpenApiSpecError(CaptureProcessingError):
    pass


class OpenApiSpecError(CaptureProcessingError):
    pass
