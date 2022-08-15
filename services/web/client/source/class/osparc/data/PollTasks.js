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
    createTask: function(taskData, interval) {
      const task = new osparc.data.PollTask(taskData, interval);
      const tasks = this.getTasks();
      const index = tasks.findIndex(t => t.getTaskId() === taskData["task_id"]);
      if (index === -1) {
        tasks.push(task);
      }
      return task;
    }
  }
});
