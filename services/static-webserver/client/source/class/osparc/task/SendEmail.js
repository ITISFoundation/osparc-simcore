/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2026 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.task.SendEmail", {
  extend: osparc.task.TaskUI,

  construct: function(subject) {
    this.base(arguments);

    this.setIcon(this.self().ICON+"/14");
    this.setTitle(this.tr("Sending Email:"));
    this.setSubtitle(subject);
  },

  statics: {
    ICON: "@FontAwesome5Solid/envelope",
  },
});
