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

qx.Class.define("osparc.task.Duplicate", {
  extend: osparc.task.TaskUI,

  construct: function(studyName) {
    this.__studyName = studyName;

    this.base(arguments);
  },

  statics: {
    ICON: "@FontAwesome5Solid/copy"
  },

  members: {
    __studyName: null,

    // overridden
    _buildLayout: function() {
      this.setIcon(this.self().ICON+"/14");
      this.getChildControl("title");
      this.getChildControl("subtitle");
      this.getChildControl("stop");

      this.setTitle(this.tr("Duplicating:"));
      this.setSubtitle(this.__studyName);
    }
  }
});
