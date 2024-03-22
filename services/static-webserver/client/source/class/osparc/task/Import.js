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

  statics: {
    ICON: "@FontAwesome5Solid/cloud-upload-alt"
  },

  members: {
    // overridden
    _buildLayout: function() {
      this.setIcon(this.self().ICON+"/14");
      this.getChildControl("title");
      this.getChildControl("subtitle");
      this.getChildControl("stop");

      this.setTitle(this.tr("Importing Study"));
    }
  }
});
