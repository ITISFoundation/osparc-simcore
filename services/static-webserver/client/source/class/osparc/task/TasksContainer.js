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

qx.Class.define("osparc.task.TasksContainer", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__tasks = new qx.data.Array();

    const tasksContainer = this.__tasksContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(3)).set({
      zIndex: osparc.utils.Utils.FLOATING_Z_INDEX,
      visibility: "excluded"
    });
    osparc.utils.Utils.setIdToWidget(tasksContainer, "tasks");
    const root = qx.core.Init.getApplication().getRoot();
    root.add(tasksContainer, {
      top: 0,
      right: 0
    });
  },

  members: {
    __tasks: null,
    __tasksContainer: null,

    addTaskUI: function(taskUI) {
      const alreadyExists = this.__tasks.filter(task => task.getTask().getTaskId() === taskUI.getTask().getTaskId()).length;
      if (alreadyExists) {
        return;
      }
      this.__tasks.push(taskUI);
      this.__tasksContainer.addAt(taskUI, 0);
    },

    removeTaskUI: function(taskUI) {
      if (this.__tasks.indexOf(taskUI) > -1) {
        this.__tasks.remove(taskUI);
      }
      if (this.__tasksContainer.indexOf(taskUI) > -1) {
        this.__tasksContainer.remove(taskUI);
      }
    },

    getTasks: function() {
      return this.__tasks;
    },

    getTasksContainer: function() {
      return this.__tasksContainer;
    },

    setTasksContainerPosition: function(x, y) {
      const root = qx.core.Init.getApplication().getRoot();
      if (root && root.getBounds()) {
        this.__tasksContainer.setLayoutProperties({
          left: x-osparc.task.TaskUI.MAX_WIDTH,
          top: y
        });
      }
    }
  }
});
