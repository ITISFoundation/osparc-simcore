/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.task.DownloadPaths", {
  extend: osparc.task.TaskUI,

  construct: function() {
    this.base(arguments);

    this.setIcon(this.self().ICON+"/14");
    this.setTitle(this.tr("Downloading files:"));
  },

  statics: {
    ICON: "@FontAwesome5Solid/download"
  },
});
