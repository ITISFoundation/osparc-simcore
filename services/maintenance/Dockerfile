#FROM nbgallery/jupyter-alpine:7.8.4
FROM jupyter/base-notebook:python-3.7.3 AS base


# COPY --chown=jovyan:users scripts/docker/healthcheck_curl_host.py /healthcheck/healthcheck_curl_host.py

# enable single-user server
RUN unset JUPYTERHUB_API_TOKEN

COPY --chown=jovyan:users packages/postgres-database $HOME/postgres-database
RUN pip install --upgrade pip wheel setuptools && \
    pip install $HOME/postgres-database[migration] && \
    rm -rf $HOME/postgres-database

WORKDIR $HOME/work
COPY --chown=jovyan:users services/maintenance/notebooks .
RUN jupyter trust db-migration.ipynb


COPY --chown=jovyan:users services/maintenance/boot.sh /usr/local/bin/
CMD [ "boot.sh" ]
