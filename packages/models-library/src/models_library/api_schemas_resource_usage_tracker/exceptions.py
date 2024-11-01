# from typing import Any

# from models_library.errors_classes import OsparcErrorMixin


# class ResourceUsageTrackerBaseError(OsparcErrorMixin, Exception):
#     def __init__(self, **ctx: Any) -> None:
#         super().__init__(**ctx)


# class InsertDBError(ResourceUsageTrackerBaseError):
#     msg_template = "Data was not inserted to the DB. Data: {data}"
