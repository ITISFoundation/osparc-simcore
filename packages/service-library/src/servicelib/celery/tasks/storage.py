from ..models import ExecutionMetadata

SEARCH_TASK_NAME = "search"
SEARCH_EXECUTION_METADATA = ExecutionMetadata(
    name=SEARCH_TASK_NAME,
    streamed_result=True,
)
