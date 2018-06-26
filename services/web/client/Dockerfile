FROM node:8.9.2 as base-stage

# Used to qx compile and/or serve (dev) client-side code

#
# + /home/scu/              $HOME
#    + client/              $PWD, WORKDIR, VOLUME( only devel)
#       + scripts/          scripts to install contributions and run entrypoint
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

# 1. qooxdoo-sdk from source repository.
#  - Provides framework and generator.py tools to overcome limits of qx-compiler
#  - This is a temporary solution
RUN git clone --depth 1 https://github.com/qooxdoo/qooxdoo.git ${QOOXDOO_PATH} && \
    sed 's/6.0.0-alpha[^"]*/'$(date +"6.0.0-alpha-%Y%m%d")'/' ${QOOXDOO_PATH}/framework/Manifest.json > ${QOOXDOO_PATH}/framework/Manifest.json.$$ && \
    mv ${QOOXDOO_PATH}/framework/Manifest.json.$$ ${QOOXDOO_PATH}/framework/Manifest.json

# 2. installs qx-compiler (see specs in package.json)
COPY --chown=scu:scu package*.json ./

RUN npm install npm@latest && \
    npm install

# owned by scu now
RUN mkdir $HOME/client
WORKDIR /home/scu/client

EXPOSE 8080

# ------------------------------------------------------------------------------------------
FROM base-stage as development

# NOTE: cannot expose contrib and source-output volumes (to keep them inside)
# within container does not work well because links remain in host

VOLUME /home/scu/client

# 3. installs contribs and qx serve -> source-output/
ENTRYPOINT ["./scripts/entrypoint.sh"]

# 4. serves
CMD ["serve"]

# ------------------------------------------------------------------------------------------
FROM base-stage as build


# 3. prepares scripts
COPY --chown=scu:scu scripts scripts
RUN chmod +x scripts/*.sh

# 4. Installs qooxdoo contributions in $WORKDIR/contrib/ within container
COPY --chown=scu:scu compile.json compile.json
RUN ./scripts/install-contrib.sh

# 5. compiles source -> build-output/
COPY --chown=scu:scu source source
COPY --chown=scu:scu Manifest.json Manifest.json
RUN qx compile --target=build

ENTRYPOINT []

CMD ["qx"]
