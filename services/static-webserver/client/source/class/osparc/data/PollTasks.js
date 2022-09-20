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
    __createTask: function(taskData, interval) {
      const task = new osparc.data.PollTask(taskData, interval);
      const tasks = this.getTasks();
      const index = tasks.findIndex(t => t.getTaskId() === taskData["task_id"]);
      if (index === -1) {
        tasks.push(task);
      }
      return task;
    },

    createPollingTask: function(fetchPromise, interval) {
      return new Promise((resolve, reject) => {
        fetchPromise
          .then(taskData => {
            if ("status_href" in taskData) {
              const task = this.__createTask(taskData, interval);
              resolve(task);
            } else {
              throw Error("Status missing");
            }
          })
          .catch(errMsg => {
            const msg = this.tr("Something went wrong Duplicating the study<br>") + errMsg;
            osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
            reject(errMsg);
          });
      });
    }
  }
});
