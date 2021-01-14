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

qx.Class.define("osparc.component.task.Tasks", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__tasks = new qx.data.Array();

    const tasksContainer = this.__tasksContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
      zIndex: 110000
    });
    osparc.utils.Utils.setIdToWidget(tasksContainer, "tasks");
    const root = qx.core.Init.getApplication().getRoot();
    root.add(tasksContainer, {
      top: 0,
      right: 0
    });

    this.__attachEventHandlers();
  },

  members: {
    __tasks: null,
    __tasksContainer: null,

    /**
     * Public function to log a FlashMessage to the user.
     *
     * @param {Object} taskObj Constructed message to log.
     */
    addTask: function(task) {
      this.__tasks.push(task);
      console.log(this.__tasks.length);
    },

    getTasks: function() {
      return this.__tasks;
    },

    getTasksContainer: function() {
      return this.__tasksContainer;
    },

    __showMessage: function(message) {
      // this.__tasksContainer.resetDecorator();
      this.__tasksContainer.add(message);
    },

    __stopTask: function(taskMsg) {
      if (this.__tasksContainer.indexOf(taskMsg) > -1) {
        // this.__tasksContainer.setDecorator("flash-container-transitioned");
        this.__tasksContainer.remove(taskMsg);
        qx.event.Timer.once(() => {
          if (this.__tasks.length) {
            // There are still messages to show
            this.__showMessage(this.__tasks.getItem(0));
          }
        }, this, 200);
      }
    },

    setTasksContainerPosition: function(x, y) {
      const root = qx.core.Init.getApplication().getRoot();
      if (root && root.getBounds()) {
        this.__tasksContainer.setLayoutProperties({
          left: x,
          top: y
        });
      }
    },

    /**
     * Function to re-position the message container according to the next message size, or its own size, if the previous is missing.
     *
     * @param {Integer} messageWidth Size of the next message to add in pixels.
     */
    __updateContainerPosition: function() {
      const root = qx.core.Init.getApplication().getRoot();
      if (root && root.getBounds()) {
        this.__tasksContainer.setLayoutProperties({
          top: 50,
          right: 100
        });
      }
    },

    __attachEventHandlers: function() {
      this.__tasks.addListener("change", e => {
        const data = e.getData();
        if (data.type === "add") {
          this.__showMessage(data.added[0]);
        }
      }, this);
    }
  }
});
