#FROM nbgallery/jupyter-alpine:7.8.4
FROM jupyter/base-notebook:python-3.7.3 AS base

COPY --chown=jovyan:users scripts/docker/healthcheck_curl_host.py /healthcheck/healthcheck_curl_host.py
HEALTHCHECK --interval=10s \
            --timeout=30s \
            --start-period=1s \
            --retries=3 \
            CMD ["python3", "/healthcheck/healthcheck_curl_host.py", "http://localhost:8888"]


# enable single-user server
RUN unset JUPYTERHUB_API_TOKEN

COPY --chown=jovyan:users services/maintenance/bin/*.sh /usr/local/bin/
COPY --chown=jovyan:users packages/postgres-database /tmp/postgres-database
COPY --chown=jovyan:users services/maintenance/requirements.txt /tmp/

RUN pip --no-cache install --upgrade pip wheel setuptools && \
    pip --no-cache install /tmp/postgres-database[migration] && \
    pip --no-cache install -r /tmp/requirements.txt &&\
    rm -rf /tmp/postgres-database && \
    rm /tmp/requirements.txt

COPY --chown=jovyan:users services/maintenance/work/ $HOME/work

WORKDIR $HOME/work
RUN jupyter trust notebooks/*; mkdir data


USER root
ENTRYPOINT ["tini", "-g", "/bin/bash", "--", "entrypoint.sh"]
CMD [ "boot.sh" ]
