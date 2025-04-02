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

qx.Class.define("osparc.store.PollTasks", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    tasks: {
      check: "Array",
      init: [],
      nullable: true,
      event: "changeTasks"
    }
  },

  members: {
    fetchTasks: function() {
      return osparc.data.Resources.get("tasks")
        .then(tasksData => {
          tasksData.forEach(taskData => {
            const interval = 1000;
            this.__addTask(taskData, interval);
          });
        })
        .catch(err => console.error(err));
    },

    createPollingTask: function(fetchPromise, interval) {
      return new Promise((resolve, reject) => {
        fetchPromise
          .then(taskData => {
            if ("status_href" in taskData) {
              const task = this.__addTask(taskData, interval);
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

    __addTask: function(taskData, interval = 1000) {
      const tasks = this.getTasks();
      const index = tasks.findIndex(t => t.getTaskId() === taskData["task_id"]);
      if (index === -1) {
        const task = new osparc.data.PollTask(taskData, interval);
        task.addListener("resultReceived", () => this.__removeTask(task), this);
        task.addListener("taskAborted", () => this.__removeTask(task), this);
        tasks.push(task);
        return task;
      }
      return null;
    },

    getDuplicateStudyTasks: function() {
      return this.getTasks().filter(task => task.getTaskId().includes("from_study") && !task.getTaskId().includes("as_template"));
    },

    getPublishTemplateTasks: function() {
      return this.getTasks().filter(task => task.getTaskId().includes("from_study") && task.getTaskId().includes("as_template"));
    },

    removeTasks: function() {
      const tasks = this.getTasks();
      tasks.forEach(task => task.dispose());
    },
  }
});
