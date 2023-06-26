# test create a job
#    - from a study
#    - from a solver
# - search jobs from a study, from a solver, etc
# - list studies  -> projects uuids that are not jobs
# - list study jobs -> projects uuids that are Jodbs

from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_metadata import projects_metadata
from simcore_postgres_database.models.projects_to_jobs import projects_to_jobs


def test_paginate_solver_jobs():
    # filter
    assert projects_to_jobs


def test_create_job():
    assert projects

    # list jobs of a study
    # list all jobs of a user
    # list projects that are non-jobs
    #


def test_create_job_metadata():
    assert projects_metadata


def test_read_job_metadata():
    ...


def test_update_job_metadata():
    ...


def test_delete_job_metadata():
    ...
