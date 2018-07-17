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

#TODO: will be replaced by pip installs
# install python requirements for simcore-sdk/s3wrapper
COPY --chown=scu:scu requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# download and install the simcore_sdk package
RUN mkdir packages && \
    cd packages && \
    git init && \
    git remote add origin -f https://github.com/ITISFoundation/osparc-simcore.git && \
    git config core.sparsecheckout true && \
    echo "packages/simcore-sdk/src/simcore_sdk/*" >> .git/info/sparse-checkout && \
    echo "packages/s3wrapper/src/s3wrapper/*" >> .git/info/sparse-checkout && \
    git pull --depth=1 origin master
ENV PYTHONPATH="./packages/packages/simcore-sdk/src:./packages/packages/s3wrapper/src"
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
# copy script to get the inputs inside the local file system
COPY --chown=scu:scu input-retriever.py input-retriever.py
# copy start script
COPY --chown=scu:scu boot.sh boot.sh
RUN chmod +x boot.sh
# get paraviewweb start script
COPY --from=dy-3dvis_paraviewweb --chown=scu:scu /startup.sh .

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
ENV CREATE_DUMMY_TABLE 1
CMD [ "/bin/bash", "boot.sh" ]
#------------------------------------------
FROM common AS production
ENTRYPOINT [ "/bin/bash", "boot.sh" ]