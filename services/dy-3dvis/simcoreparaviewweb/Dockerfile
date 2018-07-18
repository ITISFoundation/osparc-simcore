FROM dy-3dvis_paraviewweb:latest AS common

LABEL maintainer="sanderegg"

# install git
RUN apt-get update && \
    apt-get install -y \
    git python3-pip

# define user
#TODO: check with @crespo if this is correct
RUN useradd -m -U -u 8004 scu
ENV HOME /home/scu
WORKDIR /home/scu
USER scu

# set the necessary env for accessing S3/DB
#TODO: should be done with secrets
ENV SIMCORE_NODE_UUID="-1" \
    S3_ENDPOINT="=1" \
    S3_ACCESS_KEY="-1" \
    S3_SECRET_KEY="-1" \
    S3_BUCKET_NAME="-1" \
    POSTGRES_ENDPOINT="-1" \
    POSTGRES_USER="-1" \
    POSTGRES_PASSWORD="-1" \
    POSTGRES_DB="-1"

# copy start script
COPY --chown=scu:scu boot.sh boot.sh
RUN chmod +x boot.sh
# get paraviewweb start script
COPY --from=dy-3dvis_paraviewweb --chown=scu:scu /startup.sh .
#TODO: will be replaced when pip installs is available
# install python requirements for simcore-sdk/s3wrapper
COPY --chown=scu:scu requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
# set python path
ENV PYTHONPATH="./packages/packages/simcore-sdk/src:./packages/packages/s3wrapper/src"

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
#------------------------------------------
FROM common as development
VOLUME /home/scu/packages/packages/simcore-sdk/src \
    /home/scu/packages/packages/s3wrapper/src
ENV CREATE_DUMMY_TABLE 1
ENV USE_CASE_CONFIG_FILE="devel-dbconfiguration.json"
COPY --chown=scu:scu devel-dbconfiguration.json .
COPY --chown=scu:scu devel-initconfiguration.py .
CMD [ "/bin/bash", "boot.sh" ]
#------------------------------------------
FROM common AS production
#TODO: will be replaced by pip installs when available
# download and install the simcore_sdk package
RUN mkdir packages && \
    cd packages && \
    git init && \
    git remote add origin -f https://github.com/ITISFoundation/osparc-simcore.git && \
    git config core.sparsecheckout true && \
    echo "packages/simcore-sdk/src/simcore_sdk/*" >> .git/info/sparse-checkout && \
    echo "packages/s3wrapper/src/s3wrapper/*" >> .git/info/sparse-checkout && \
    git pull --depth=1 origin master
# copy script to get the inputs inside the local file system
COPY --chown=scu:scu input-retriever.py input-retriever.py
ENTRYPOINT [ "/bin/bash", "boot.sh" ]