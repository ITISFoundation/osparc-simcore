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

  construct: function(subject = "") {
    this.base(arguments);

    this.setIcon(this.self().ICON+"/14");
    this.setTitle(this.tr("Sending Email:"));
    this.setSubtitle(subject);
  },

  statics: {
    ICON: "@FontAwesome5Solid/envelope",

    sendEmailTaskReceived: function(task, subject = "") {
      const sendEmailTaskUI = new osparc.task.SendEmail(subject);
      sendEmailTaskUI.setTask(task);
      osparc.task.TasksContainer.getInstance().addTaskUI(sendEmailTaskUI);

      task.addListener("resultReceived", () => {
        osparc.FlashMessenger.logAs(this.tr("Email(s) sent successfully"), "INFO");
      });

      task.addListener("taskAborted", () => {
        osparc.FlashMessenger.logAs(qx.locale.Manager.tr("Email(s) cancelled"), "WARNING");
      });

      task.addListener("pollingError", e => {
        osparc.FlashMessenger.logError(e.getData());
      });
    },
  }
});
