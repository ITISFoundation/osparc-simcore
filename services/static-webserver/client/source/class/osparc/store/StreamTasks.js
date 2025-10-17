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

  members: {
    getStreamTask: function(action, params, streamPromise, interval) {
      const internalId = action + "_" + JSON.stringify(params);
      const task = this.__getStreamTask(internalId);
      if (task) {
        console.log("Reusing existing stream task:", internalId);
        return Promise.resolve(task);
      }
      return this.__createStreamTask(internalId, streamPromise, interval)
        .then(streamTask => {
          console.log("Creating new stream task:", internalId);
          return streamTask;
        })
        .catch(err => Promise.reject(err));
    },

    __createStreamTask: function(internalId, streamPromise, interval) {
      return streamPromise
        .then(streamData => {
          console.log("Stream data received:", streamData);
          if (!("stream_href" in streamData)) {
            throw new Error("Stream href missing");
          }
          return this.__addStreamTask(internalId, streamData, interval);
        })
        .catch(err => Promise.reject(err));
    },

    __getStreamTask: function(internalId) {
      const tasks = this.getTasks();
      return tasks[internalId] || null;
    },

    __addStreamTask: function(internalId, streamData, interval) {
      const task = this.__getStreamTask(internalId);
      if (task) {
        return task;
      }

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
