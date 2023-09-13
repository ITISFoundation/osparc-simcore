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

qx.Class.define("osparc.task.Import", {
  extend: osparc.task.TaskUI,

  construct: function(study) {
    this.__study = study;

    this.base(arguments);
  },

  members: {
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

    // overridden
    _buildLayout: function() {
      this.getChildControl("icon");
      this.getChildControl("title");
      this.getChildControl("subtitle");
      this.getChildControl("stop");

      this.setTitle(this.tr("Importing Study"));
    }
  }
});
