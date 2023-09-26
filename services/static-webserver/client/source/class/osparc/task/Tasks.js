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

qx.Class.define("osparc.task.Tasks", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__tasks = new qx.data.Array();

    const tasksContainer = this.__tasksContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(3)).set({
      zIndex: 110000,
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

    addTask: function(task) {
      this.__tasks.push(task);
      this.__tasksContainer.addAt(task, 0);
    },

    removeTask: function(task) {
      if (this.__tasks.indexOf(task) > -1) {
        this.__tasks.remove(task);
      }
      if (this.__tasksContainer.indexOf(task) > -1) {
        this.__tasksContainer.remove(task);
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
