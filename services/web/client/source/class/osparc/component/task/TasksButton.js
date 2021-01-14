/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.task.TasksButton", {
  extend: qx.ui.basic.Image,

  construct: function() {
    this.base(arguments, "@FontAwesome5Solid/cog/24");

    this.setCursor("pointer");

    const tasks = osparc.component.task.Tasks.getInstance();
    tasks.getTasks().addListener("change", () => {
      this.__showTasksButton(tasks.getTasks().length);
    }, this);
    this.__showTasksButton(tasks.getTasks().length);

    this.addListener("tap", () => {
      this.__showTasks();
    }, this);
  },

  members: {
    __showTasksButton: function(show) {
      if (show) {
        this.show();
        this.getContentElement().addClass("rotate");
      } else {
        this.exclude();
        this.getContentElement().removeClass("rotate");
      }
    },

    __showTasks: function() {
      const bounds = this.getBounds();
      const tasks = osparc.component.task.Tasks.getInstance();
      tasks.setTasksContainerPosition(bounds.left, 50);
      tasks.getTasksContainer().show();
    },

    __hideTasks: function() {
      const tasks = osparc.component.task.Tasks.getInstance();
      tasks.getTasksContainer().exclude();
    }
  }
});
