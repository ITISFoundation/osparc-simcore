FROM python:3.6-slim as base

LABEL maintainer=sanderegg

# Sets utf-8 encoding for Python et al
ENV LANG=C.UTF-8
# Turns off writing .pyc files; superfluous on an ephemeral container.
ENV PYTHONDONTWRITEBYTECODE=1 \
  VIRTUAL_ENV=/home/scu/.venv
# Ensures that the python and pip executables used
# in the image will be those from our virtualenv.
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"


FROM base as build

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential \
    git \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*


# NOTE: python virtualenv is used here such that installed packages may be moved to production image easily by copying the venv
RUN python -m venv "${VIRTUAL_ENV}"

RUN pip --no-cache-dir install --upgrade \
  pip~=23.0  \
  wheel \
  setuptools

ARG GIT_BRANCH
ARG GIT_REPOSITORY

RUN git clone --single-branch --branch ${GIT_BRANCH} ${GIT_REPOSITORY} osparc-simcore\
  && pip install osparc-simcore/packages/postgres-database[migration]

FROM base as production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# bring installed package without build tools
COPY --from=build ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY entrypoint.bash /home/entrypoint.bash

RUN chmod +x /home/entrypoint.bash

ENV POSTGRES_USER=scu \
  POSTGRES_PASSWORD=adminadmin \
  POSTGRES_HOST=postgres \
  POSTGRES_PORT=5432 \
  POSTGRES_DB=simcoredb

ENTRYPOINT [ "/bin/bash", "/home/entrypoint.bash" ]
CMD [ "sc-pg", "upgrade" ]
