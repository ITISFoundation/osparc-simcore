from ._models import OperationType
from ._utils import get_scheduler_oepration_name

# SHARED

ENFORCE = get_scheduler_oepration_name(OperationType.ENFORCE, "shared")


# NEW STYLE

NEW_STYLE_START = get_scheduler_oepration_name(OperationType.START, "new_style")
NEW_STYLE_STOP = get_scheduler_oepration_name(OperationType.STOP, "new_style")
NEW_STYLE_MONITOR = get_scheduler_oepration_name(OperationType.MONITOR, "new_style")


# LEGACY

LEGACY_START = get_scheduler_oepration_name(OperationType.START, "legacy")
LEGACY_STOP = get_scheduler_oepration_name(OperationType.STOP, "legacy")
LEGACY_MONITOR = get_scheduler_oepration_name(OperationType.MONITOR, "legacy")
