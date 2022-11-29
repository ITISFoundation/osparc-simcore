""" Studies collections


"""

#
# studies/{project_id}
#

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


def list_study_ports():
    # GET /projects/{project_id}/inputs
    pass


#
# studies/{project_id}/jobs/{job_id}
#


def get_study_job_inputs():
    # GET /projects/{project_id}/inputs
    # Envelope[dict[uuid.UUID, simcore_service_webserver.projects.projects_ports_handlers.ProjectPortGet]]
    pass


def update_study_job_inputs():
    # PATCH /projects/{project_id}/inputs
    # Envelope[dict[uuid.UUID, simcore_service_webserver.projects.projects_ports_handlers.ProjectPortGet]]
    pass


def get_study_job_outputs():
    # GET /projects/{project_id}/outputs
    # Envelope[dict[uuid.UUID, simcore_service_webserver.projects.projects_ports_handlers.ProjectPortGet]]
    pass
