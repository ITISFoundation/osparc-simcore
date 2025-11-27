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
      init: null,
    },

    end: {
      check: "Boolean",
      nullable: false,
      init: false,
    },

    pageSize: {
      check: "Number",
      nullable: false,
      init: 5,
    },
  },

  members: {
    // override
    _startPolling: function() {
      return;
    },

    fetchStream: function() {
      return new Promise((resolve, reject) => {
        if (!this.isEnd()) {
          const streamPath = osparc.data.PollTask.extractPathname(this.getStreamHref());
          const url = `${streamPath}?limit=${this.getPageSize()}`;
          fetch(url)
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
              const end = streamData["data"]["end"] || false;
              if (end) {
                this.setEnd(true);
              }
              if ("data" in streamData && streamData["data"]) {
                resolve(streamData);
              }
              throw new Error("Missing stream data");
            })
            .catch(err => {
              this.fireDataEvent("pollingError", err);
              reject(err);
            });
        }
      });
    },
  }
});
