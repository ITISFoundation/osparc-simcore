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

qx.Class.define("osparc.component.task.Import", {
  extend: osparc.component.task.Task,

  construct: function() {
    this.base(arguments);

    this.__builyLayout();
  },

  members: {
    __study: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          // control = new qx.ui.basic.Image("@FontAwesome5Solid/file-import/14");
          control = new qx.ui.basic.Image("@FontAwesome5Solid/cloud-upload-alt/14").set({
            alignY: "middle",
            alignX: "center",
            paddingLeft: 3,
            width: 25
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __builyLayout: function() {
      this.getChildControl("icon");

      const label = this.getChildControl("label");
      label.setValue(this.tr("Importing Study"));

      this.getChildControl("stop");
    },

    // overridden
    _stopTask: function() {
      console.log("Stop importing");
      const tasks = osparc.component.task.Tasks.getInstance();
      tasks.removeTask(this);
    }
  }
});
