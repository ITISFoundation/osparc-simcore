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
      width: 30,
      alignX: "center",
      cursor: "pointer",
      visibility: "excluded",
      toolTipText: this.tr("Tasks"),
    });

    const tasks = osparc.task.TasksContainer.getInstance();
    tasks.getTasks().addListener("change", e => this.__updateTasksButton(), this);
    this.addListener("tap", () => this.__showTasks(), this);
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
            bottom: 8,
            right: 4
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
      number.setValue(nTasks.toString());
      nTasks ? this.show() : this.exclude();
    },

    __showTasks: function() {
      const that = this;
      const tapListener = event => {
        const tasks = osparc.task.TasksContainer.getInstance();
        const tasksContainer = tasks.getTasksContainer();
        if (osparc.utils.Utils.isMouseOnElement(tasksContainer, event)) {
          return;
        }
        // eslint-disable-next-line no-underscore-dangle
        that.__hideTasks();
        document.removeEventListener("mousedown", tapListener);
      };

      const bounds = this.getBounds();
      const cel = this.getContentElement();
      if (cel) {
        const domeEle = cel.getDomElement();
        if (domeEle) {
          const rect = domeEle.getBoundingClientRect();
          bounds.left = parseInt(rect.x);
          bounds.top = parseInt(rect.y);
        }
      }
      const tasks = osparc.task.TasksContainer.getInstance();
      tasks.setTasksContainerPosition(
        bounds.left + bounds.width - osparc.task.TaskUI.MAX_WIDTH,
        osparc.navigation.NavigationBar.HEIGHT + 14
      );
      tasks.getTasksContainer().show();
      document.addEventListener("mousedown", tapListener);
    },

    __hideTasks: function() {
      const tasks = osparc.task.TasksContainer.getInstance();
      tasks.getTasksContainer().exclude();
    }
  }
});
