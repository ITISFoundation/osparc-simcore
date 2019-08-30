FROM node:10.15.1 as base-stage

# Used to qx compile and/or serve (dev) client-side code

#
# + /home/scu/              $HOME
#    + client/              $PWD, WORKDIR, VOLUME( only devel)
#       + docker/          scripts and config to install packages and run entrypoint
#       + source/
#       + source-output/    $QOOXDOO_OUTDIR
#       + packages.json     specifies qx-compiler
#       + ...
#    + .npm-global/         global npm folder
#       + bin/           *
#    + node_modules/        local npm folder
#       + .bin/          *
#            - qx           qx compiler executable
#    + qooxdoo-sdk/         $QOOXDOO_PATH
#       + framework         contains qx library
#       + tool/
#           + bin/       *  contains generator.py
#
#  * = in $PATH
#
LABEL maintainer=pcrespov

# non-root user uid=1000
# TODO: create instead uid=5000.
RUN groupmod --new-name scu node && \
    usermod --login scu --move-home --home /home/scu node
USER scu


ENV HOME /home/scu
ENV NPM_CONFIG_LOGLEVEL warn
ENV NPM_CONFIG_PREFIX $HOME/.npm-global
ENV QOOXDOO_PATH $HOME/qooxdoo-sdk
ENV QOOXDOO_OUTDIR $HOME/client/source-output
ENV PATH "${QOOXDOO_PATH}/tool/bin:${HOME}/node_modules/.bin/:${NPM_CONFIG_PREFIX}/bin:${PATH}"


WORKDIR /home/scu

# 1. installs qx-compiler (see specs in package.json)
COPY --chown=scu:scu package*.json ./

RUN npm install -g npm@latest && \
    npm install

# owned by scu now
RUN mkdir $HOME/client
WORKDIR /home/scu/client

EXPOSE 8080

# ------------------------------------------------------------------------------------------
FROM base-stage as development

# NOTE: cannot expose packages and source-output volumes (to keep them inside)
# within container does not work well because links remain in host

VOLUME /home/scu/client

# 3. installs packages and qx serve -> source-output/
# NOTE: expects docker available via volume bound
ENTRYPOINT ["./docker/entrypoint.sh"]

# 4. serves
CMD ["serve", "--set", "qx.allowUrlSettings=true"]

# ------------------------------------------------------------------------------------------
FROM base-stage as build

# 3. prepares docker
COPY --chown=scu:scu docker docker
RUN chmod +x docker/*.sh

# 4. Installs qooxdoo packages in $WORKDIR/qx_packages/ within container
COPY --chown=scu:scu compile.json compile.json
COPY --chown=scu:scu qx-lock.json qx-lock.json
RUN ./docker/install-contrib.sh

# 5. compiles source -> build-output/
COPY --chown=scu:scu source source
COPY --chown=scu:scu Manifest.json Manifest.json

ARG VCS_URL
ARG VCS_REF
ARG VCS_REF_CLIENT
ARG VCS_STATUS_CLIENT

RUN qx compile --target=build \
        --set osparc.vcsOriginUrl=\"${VCS_URL}\" \
        --set osparc.vcsRef=\"${VCS_REF}\" \
        --set osparc.vcsRefClient=\"${VCS_REF_CLIENT}\" \
        --set osparc.vcsStatusClient=\"${VCS_STATUS_CLIENT}\"

ENTRYPOINT []
CMD []
