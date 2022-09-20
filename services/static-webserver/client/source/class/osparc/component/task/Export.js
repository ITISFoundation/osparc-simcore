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
    this.__study = study;

    this.base(arguments);
  },

  statics: {
    EXPORT_ICON: "@FontAwesome5Solid/cloud-download-alt" // "@FontAwesome5Solid/file-export"
  },

  members: {
    __study: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          control = new qx.ui.basic.Image(this.self().EXPORT_ICON+"/14").set({
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

    // overridden
    _buildLayout: function() {
      this.getChildControl("icon");
      this.getChildControl("title");
      this.getChildControl("subtitle");
      this.getChildControl("stop");

      this.setTitle(this.tr("Exporting ") + this.__study.name);
    },

    // overridden
    _requestStop: function() {
      console.log("Not yet implemented");
    }
  }
});
