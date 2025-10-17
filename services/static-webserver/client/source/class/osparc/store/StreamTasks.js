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
        return Promise.resolve(task);
      }
      return this.__createStreamTask(internalId, streamPromise, interval);
    },

    __createStreamTask: function(internalId, streamPromise, interval) {
      return new Promise((resolve, reject) => {
        streamPromise
          .then(streamData => {
            if ("status_href" in streamData) {
              const task = this.__addStreamTask(internalId, streamData, interval);
              resolve(task);
            } else {
              throw Error("Status missing");
            }
          })
          .catch(err => reject(err));
      });
    },

    __getStreamTask: function(internalId) {
      const tasks = this.getTasks();
      if (internalId in tasks) {
        return tasks[internalId];
      }
      return null;
    },

    __addStreamTask: function(internalId, streamData, interval) {
      const task = this.__getStreamTask(internalId);
      if (task) {
        return task;
      }

      const stream = new osparc.data.StreamTask(streamData, interval);
      stream.addListener("resultReceived", () => this.__removeStreamTask(stream), this);
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
