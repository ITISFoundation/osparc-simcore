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

qx.Class.define("osparc.task.Export", {
  extend: osparc.task.TaskUI,

  construct: function(study) {
    this.__study = study;

    this.base(arguments);
  },

  statics: {
    ICON: "@FontAwesome5Solid/cloud-download-alt"
  },

  members: {
    __study: null,

    // overridden
    _buildLayout: function() {
      this.setIcon(this.self().ICON+"/14");
      this.getChildControl("title");
      this.getChildControl("subtitle");
      this.getChildControl("stop");

      this.setTitle(this.tr("Exporting ") + this.__study.name);
    }
  }
});
