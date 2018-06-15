FROM client_qx:build as qx-build-stage

ENV QOOXDOO_OUTDIR $HOME/client/source-output


# ------------------------------------------------------------------------------------------
FROM python:3.6-alpine

RUN useradd -r -u 1001 -g scu scu
USER scu


ENV HOME /home/scu
ENV SIMCORE_WEB_OUTDIR=$HOME/client



COPY --from=qx-stage ${QOOXDOO_OUTDIR} ${SIMCORE_WEB_OUTDIR}
