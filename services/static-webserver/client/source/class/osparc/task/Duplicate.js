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
    this.base(arguments);

    this.setIcon(this.self().ICON+"/14");
    this.setTitle(this.tr("Duplicating:"));
    this.setSubtitle(studyName);
  },

  statics: {
    ICON: "@FontAwesome5Solid/copy"
  },
});
