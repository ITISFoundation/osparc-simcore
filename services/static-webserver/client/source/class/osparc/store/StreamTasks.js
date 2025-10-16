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
    createStreamTask: function(streamPromise, interval) {
      return new Promise((resolve, reject) => {
        streamPromise
          .then(streamData => {
            if ("status_href" in streamData) {
              const task = this.__addTask(streamData, interval);
              resolve(task);
            } else {
              throw Error("Status missing");
            }
          })
          .catch(err => reject(err));
      });
    },

    __removeTask: function(task) {
      const tasks = this.getTasks();
      const index = tasks.findIndex(t => t.getTaskId() === task.getTaskId());
      if (index > -1) {
        tasks.splice(index, 1);
      }
    },

    __addTask: function(streamData, interval) {
      const tasks = this.getTasks();
      if (streamData["task_id"] in tasks) {
        return tasks[streamData["task_id"]];
      }

      const stream = new osparc.data.StreamTask(streamData, interval);
      stream.addListener("resultReceived", () => this.__removeTask(stream), this);
      stream.addListener("taskAborted", () => this.__removeTask(stream), this);
      tasks[stream.getTaskId()] = stream;
      return stream;
    },

    fetchStream: function(taskId) {
      const tasks = this.getTasks();
      if (taskId in tasks) {
        const task = tasks[taskId];
        task.fetchStream();
      }
    },
  }
});
