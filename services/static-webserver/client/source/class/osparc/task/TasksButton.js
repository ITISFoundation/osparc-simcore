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

qx.Class.define("osparc.task.TasksButton", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      toolTipText: this.tr("Tasks"),
    });

    const tasks = osparc.task.TasksContainer.getInstance();
    tasks.getTasks().addListener("change", () => this.__updateTasksButton(), this);
    this.__updateTasksButton();

    this.addListener("tap", this.__buttonTapped, this);
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new qx.ui.basic.Image("@FontAwesome5Solid/cog/22");
          osparc.utils.Utils.addClass(control.getContentElement(), "rotateSlow");

          const logoContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignY: "middle"
          }));
          logoContainer.add(control);

          this._add(logoContainer, {
            height: "100%"
          });
          break;
        }
        case "number":
          control = new qx.ui.basic.Label().set({
            backgroundColor: osparc.navigation.NavigationBar.BG_COLOR,
            paddingLeft: 4,
            font: "text-12"
          });
          control.getContentElement().setStyles({
            "border-radius": "8px"
          });
          this._add(control, {
            bottom: -6,
            right: -4
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __updateTasksButton: function() {
      this.getChildControl("icon");
      const number = this.getChildControl("number");

      const tasks = osparc.task.TasksContainer.getInstance();
      const nTasks = tasks.getTasks().length;
      if (nTasks > 9) {
        number.setValue("9+");
      } else {
        number.setValue(nTasks.toString());
      }
      nTasks ? this.show() : this.exclude();
    },

    __buttonTapped: function() {
      const tasks = osparc.task.TasksContainer.getInstance();
      const tasksContainer = tasks.getTasksContainer();
      if (tasksContainer && tasksContainer.isVisible()) {
        this.__hideTasks();
      } else {
        this.__showTasks();
      }
    },

    __showTasks: function() {
      this.__positionTasksContainer();

      const tasks = osparc.task.TasksContainer.getInstance();
      tasks.getTasksContainer().show();

      // Add listeners for taps outside the container to hide it
      document.addEventListener("mousedown", this.__onTapOutsideMouse.bind(this), true);
    },

    __positionTasksContainer: function() {
      const bounds = osparc.utils.Utils.getBounds(this);
      const tasks = osparc.task.TasksContainer.getInstance();
      tasks.setTasksContainerPosition(
        bounds.left + bounds.width - osparc.task.TaskUI.MAX_WIDTH - 2*8,
        osparc.navigation.NavigationBar.HEIGHT - 8
      );
    },

    __onTapOutsideMouse: function(event) {
      this.__handleOutsideEvent(event);
    },

    __handleOutsideEvent: function(event) {
      const tasks = osparc.task.TasksContainer.getInstance();
      const onContainer = osparc.utils.Utils.isMouseOnElement(tasks.getTasksContainer(), event);
      const onButton = osparc.utils.Utils.isMouseOnElement(this, event);
      if (!onContainer && !onButton) {
        this.__hideTasks();
      }
    },

    __hideTasks: function() {
      const tasks = osparc.task.TasksContainer.getInstance();
      tasks.getTasksContainer().exclude();

      // Remove listeners for outside clicks/taps
      document.removeEventListener("mousedown", this.__onTapOutsideMouse.bind(this), true);
    }
  }
});
