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

qx.Class.define("osparc.store.StreamTasks", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    tasks: {
      check: "Object",
      init: {},
      nullable: false,
    }
  },

  statics: {
    actionToInternalId: function(action, params) {
      return action + "_" + JSON.stringify(params);
    },
  },

  members: {
    createStreamTask: function(action, params, streamPromise, interval) {
      return streamPromise
        .then(streamData => {
          console.log("Stream data received:", streamData);
          if (!("stream_href" in streamData)) {
            throw new Error("Stream href missing");
          }
          return this.__addStreamTask(action, params, streamData, interval);
        })
        .catch(err => Promise.reject(err));
    },

    getStreamTask: function(action, params) {
      const internalId = osparc.store.StreamTasks.actionToInternalId(action, params);
      const tasks = this.getTasks();
      return tasks[internalId] || null;
    },

    __addStreamTask: function(action, params, streamData, interval) {
      const internalId = osparc.store.StreamTasks.actionToInternalId(action, params);
      const stream = new osparc.data.StreamTask(streamData, interval);
      // stream.addListener("resultReceived", () => this.__removeStreamTask(stream), this);
      stream.addListener("taskAborted", () => this.__removeStreamTask(stream), this);
      const tasks = this.getTasks();
      tasks[internalId] = stream;
      return stream;
    },

    __removeStreamTask: function(stream) {
      const tasks = this.getTasks();
      const index = tasks.findIndex(t => t.getTaskId() === stream.getTaskId());
      if (index > -1) {
        tasks.splice(index, 1);
      }
    },
  }
});
