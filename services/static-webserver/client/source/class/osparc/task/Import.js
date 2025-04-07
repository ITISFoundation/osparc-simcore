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

  construct: function(studyName) {
    this.base(arguments);

    this.setIcon(this.self().ICON+"/14");
    this.setTitle(this.tr("Importing..."));
    this.setSubtitle(studyName);
  },

  statics: {
    ICON: "@FontAwesome5Solid/cloud-upload-alt"
  },
});
