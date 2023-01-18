from pydantic import BaseModel

StepName = str
ActionName = str
WorkflowName = str


class ExceptionInfo(BaseModel):
    exception_class: type
    action_name: ActionName
    step_name: StepName
    serialized_traceback: str
