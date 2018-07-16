FROM dy-3dvis_paraviewweb:latest AS common

LABEL maintainer="sanderegg"

#TODO: check with @crespo if this is correct
RUN useradd -m -U scu
ENV HOME /home/scu
WORKDIR /home/scu

# install git
RUN apt-get update && \
    apt-get install -y \
    git

# install requirements, install jupyter notebook extensions and enable necessary ones
COPY --chown=scu:scu requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

USER scu

# download the simcore_sdk package
RUN mkdir packages && \
    cd packages && \
    git init && \
    git remote add origin -f https://github.com/ITISFoundation/osparc-simcore.git && \
    git config core.sparsecheckout true && \
    echo "packages/simcore-sdk/src/simcore_sdk/*" >> .git/info/sparse-checkout && \
    echo "packages/s3wrapper/src/s3wrapper/*" >> .git/info/sparse-checkout && \
    git pull --depth=1 origin master

ENV PYTHONPATH="./packages/packages/simcore-sdk/src:./packages/packages/s3wrapper/src"

ENV SIMCORE_NODE_UUID="-1" \
    S3_ENDPOINT="=1" \
    S3_ACCESS_KEY="-1" \
    S3_SECRET_KEY="-1" \
    S3_BUCKET_NAME="-1" \
    POSTGRES_ENDPOINT="-1" \
    POSTGRES_USER="-1" \
    POSTGRES_PASSWORD="-1" \
    POSTGRES_DB="-1"

# Labels.
ARG VCS_REF
ARG BUILD_DATE
LABEL org.label-schema.schema-version="1.0" \
    org.label-schema.build-date=${BUILD_DATE} \
    org.label-schema.url="https://www.itis.ethz.ch" \
    org.label-schema.vcs-url="https://github.com/ITISFoundation/osparc-simcore" \
    org.label-schema.vcs-ref=${VCS_REF} \
    org.label-schema.vendor="IT'IS foundation"
# service runtime settings
LABEL simcore.service.settings='[{"name": "ports", "type": "int", "value": 8777}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}]'

COPY --chown=scu:scu input-retriever.py input-retriever.py
COPY --chown=scu:scu boot.sh boot.sh
RUN chmod +x boot.sh

COPY --from=dy-3dvis_paraviewweb --chown=scu:scu /startup.sh .

ENTRYPOINT [ "/bin/sh", "boot.sh" ]