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
      // init: 20,
      init: 2,
    },
  },

  members: {
    _startPolling: function() {
      this.fetchStream();
    },

    fetchStream: function() {
      if (!this.isDone()) {
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
            if ("data" in streamData && streamData["data"]) {
              const items = streamData["data"]["items"] || [];
              const end = streamData["data"]["end"] || false;
              if (items.length === 0 && end === false) {
                // nothing to stream yet, try again later
                setTimeout(() => this.fetchStream(), this.getPollInterval());
                return;
              }
              this.fireDataEvent("streamReceived", items);
              if (end) {
                this.setEnd(true);
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
