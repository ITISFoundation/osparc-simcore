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
    this.base(arguments);

    this.setIcon(this.self().ICON+"/14");
    this.setTitle(this.tr("Exporting:"));
    this.setSubtitle(study.name);
  },

  statics: {
    ICON: "@FontAwesome5Solid/cloud-download-alt"
  },
});
