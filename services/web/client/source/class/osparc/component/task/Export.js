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

qx.Class.define("osparc.component.task.Export", {
  extend: osparc.component.task.Task,

  construct: function(study) {
    this.base(arguments);

    this.__study = study;

    this.__builyLayout();
  },

  members: {
    __study: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          // control = new qx.ui.basic.Image("@FontAwesome5Solid/file-export/14");
          control = new qx.ui.basic.Image("@FontAwesome5Solid/cloud-download-alt/14").set({
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
      label.setValue(this.tr("Exporting: ") + this.__study.name);

      this.getChildControl("stop");
    },

    // overridden
    _stopTask: function() {
      console.log("Stop exporting", this.__study.name);
      const tasks = osparc.component.task.Tasks.getInstance();
      tasks.removeTask(this);
    }
  }
});
