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

qx.Class.define("osparc.message.Messages", {
  type: "static",

  statics: {
    fetchEmailTemplates: function() {
      return osparc.store.Faker.getInstance().fetchEmailTemplates();
      // return osparc.data.Resources.fetch("notificationTemplates", "getTemplates");
    },

    fetchEmailPreview: function(templateId, context = {}) {
      return osparc.store.Faker.getInstance().fetchEmailPreview(templateId, context);
      // return osparc.data.Resources.fetch("notificationTemplates", "getTemplatePreview")
    },

    sendMessageFromTemplate: function(data) {
      const params = {
        data,
      };
      return osparc.data.Resources.fetch("sendMessageFromTemplate", "post", params);
    },

    sendMessage: function(data) {
      return new Promise((resolve) => resolve());
      const params = {
        data,
      };
      return osparc.data.Resources.fetch("sendMessage", "post", params);
    },
  }
});
