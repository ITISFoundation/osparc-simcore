from models_library.projects import ProjectID
from models_library.rest_base import StrictRequestParameters


class StudyDispatchPathParams(StrictRequestParameters):
    study_id: ProjectID
