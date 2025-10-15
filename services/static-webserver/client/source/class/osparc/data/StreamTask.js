/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @ignore(fetch)
 */

qx.Class.define("osparc.data.StreamTask", {
  extend: osparc.data.PollTask,

  construct: function(streamData, interval = 500) {
    this.set({
      streamHref: streamData["stream_href"] || null,
    });

    this.base(arguments, streamData, interval);
  },

  events: {
    "streamReceived": "qx.event.type.Data",
  },

  properties: {
    streamHref: {
      check: "String",
      nullable: false,
    },
  },

  members: {
    _startPolling: function() {
      this.__fetchStream();
    },

    __fetchStream: function() {
      if (!this.isDone()) {
        const streamPath = osparc.data.PollTask.extractPathname(this.getStreamHref());
        fetch(streamPath)
          .then(resp => {
            if (resp.status === 200) {
              return resp.json();
            }
            const errMsg = qx.locale.Manager.tr("Unsuccessful streaming");
            const err = new Error(errMsg);
            this.fireDataEvent("pollingError", err);
            throw err;
          })
          .then(streamData => {
            if ("error" in streamData && streamData["error"]) {
              throw streamData["error"];
            }
            if ("data" in streamData && streamData["data"]) {
              const data = streamData["data"];
              this.fireDataEvent("streamReceived", data);
              if ("end" in data && data["end"] === false) {
                setTimeout(() => this.__fetchStream(), this.getPollInterval());
              } else {
                this.setDone(true);
              }
              return;
            }
            throw new Error("Missing stream data");
          })
          .catch(err => {
            this.fireDataEvent("pollingError", err);
            throw err;
          });
      }
    },
  }
});
