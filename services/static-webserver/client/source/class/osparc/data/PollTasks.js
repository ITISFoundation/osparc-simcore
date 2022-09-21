/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.data.PollTasks", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.initTasks();
  },

  properties: {
    tasks: {
      check: "Array",
      init: [],
      nullable: true,
      event: "changeTasks"
    }
  },

  members: {
    addTask: function(taskData, interval) {
      const task = new osparc.data.PollTask(taskData, interval);
      const tasks = this.getTasks();
      const index = tasks.findIndex(t => t.getTaskId() === taskData["task_id"]);
      if (index === -1) {
        tasks.push(task);
        return task;
      }
      return null;
    },

    createPollingTask: function(fetchPromise, interval) {
      return new Promise((resolve, reject) => {
        fetchPromise
          .then(taskData => {
            if ("status_href" in taskData) {
              const task = this.addTask(taskData, interval);
              resolve(task);
            } else {
              throw Error("Status missing");
            }
          })
          .catch(errMsg => reject(errMsg));
      });
    }
  }
});
