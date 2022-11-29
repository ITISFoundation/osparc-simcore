""" Studies collections


"""


# CRUD
def create_study():
    pass


def list_studies():
    pass


def get_study():
    pass


def replace_study():
    pass


def update_study():
    pass


def delete_study():
    pass


# Sub-Resources ports and inputs/outputs


def list_study_ports():
    # as similar as possible to list[SolverPort]
    # refers to the json-schema (semantics)
    # this connects with /home/crespo/devp/osparc-simcore/services/web/server/src/simcore_service_webserver/projects/projects_ports_handlers.py
    pass


def get_study_inputs():
    # GET /projects/{project_id}/inputs
    # Envelope[dict[uuid.UUID, simcore_service_webserver.projects.projects_ports_handlers.ProjectPortGet]]
    pass


def update_study_inputs():
    # PATCH /projects/{project_id}/inputs
    # Envelope[dict[uuid.UUID, simcore_service_webserver.projects.projects_ports_handlers.ProjectPortGet]]
    pass


def get_study_outputs():
    # GET /projects/{project_id}/outputs
    # Envelope[dict[uuid.UUID, simcore_service_webserver.projects.projects_ports_handlers.ProjectPortGet]]
    pass
