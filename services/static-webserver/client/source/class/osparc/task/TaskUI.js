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

qx.Class.define("osparc.task.TaskUI", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    });
    this._setLayout(layout);

    this.set({
      height: 30,
      maxWidth: this.self().MAX_WIDTH,
      backgroundColor: "material-button-background"
    });

    this._buildLayout();
  },

  properties: {
    task: {
      check: "osparc.data.PollTask",
      init: null,
      nullable: false,
      apply: "__applyTask"
    },

    title: {
      check: "String",
      init: "",
      nullable: true,
      event: "changeTitle"
    },

    subtitle: {
      check: "String",
      init: "",
      nullable: true,
      event: "changeSubtitle"
    }
  },

  statics: {
    MAX_WIDTH: 300
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          control = new osparc.ui.form.FetchButton().set({
            width: 25
          });
          this._add(control);
          break;
        case "title":
          control = new qx.ui.basic.Label();
          this.bind("title", control, "value");
          this._add(control);
          break;
        case "subtitle":
          control = new qx.ui.basic.Label().set({
            allowGrowX: true
          });
          this.bind("subtitle", control, "value");
          this._add(control, {
            flex: 1
          });
          break;
        case "stop":
          control = new qx.ui.basic.Image("@MaterialIcons/close/16").set({
            alignY: "middle",
            alignX: "center",
            width: 25,
            cursor: "pointer",
            visibility: "excluded"
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyTask: function(task) {
      const stopButton = this.getChildControl("stop");
      task.bind("abortHref", stopButton, "visibility", {
        converter: abortHref => abortHref ? "visible" : "excluded"
      });
      stopButton.addListener("tap", () => {
        const msg = this.tr("Are you sure you want to cancel the task?");
        const win = new osparc.ui.window.Confirmation(msg).set({
          confirmText: this.tr("Cancel"),
          confirmAction: "delete"
        });
        win.getCancelButton().setLabel(this.tr("Ignore"));
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            task.abortRequested();
          }
        }, this);
      }, this);
    },

    start: function() {
      const tasks = osparc.task.Tasks.getInstance();
      tasks.addTask(this);
    },

    stop: function() {
      const tasks = osparc.task.Tasks.getInstance();
      tasks.removeTask(this);
    },

    /**
      * @abstract
      */
    _buildLayout: function() {
      throw new Error("Abstract method called!");
    }
  }
});
