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

  construct: function(taskData, interval = 2000) {
    this.set({
      streamHref: taskData["stream_href"] || null,
    });

    this.base(arguments, taskData, interval);
  },

  events: {
    "streamReceived": "qx.event.type.Data",
  },

  properties: {
    resultHref: {
      refine: true,
      nullable: true
    },

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
        const streamPath = this.self().extractPathname(this.getStreamHref());
        fetch(streamPath)
          .then(streamData => {
            if ("error" in streamData && streamData["error"]) {
              throw streamData["error"];
            }
            if ("data" in streamData && streamData["data"]) {
              const data = streamData["data"];
              this.fireDataEvent("streamReceived", data);
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
