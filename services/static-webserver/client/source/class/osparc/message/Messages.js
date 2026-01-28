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
      return osparc.data.Resources.fetch("notificationTemplates", "getEmailTemplates");
    },

    fetchEmailPreview: function(templateName, context = {}) {
      return osparc.store.Faker.getInstance().fetchEmailPreview(templateName, context);
      const params = {
        data: {
          "ref:": {
            "channel": "email",
            "templateName": templateName,
          },
          "context": context,
        },
      };
      return osparc.data.Resources.fetch("notificationTemplates", "getTemplatePreview")
    },

    sendMessage: function(recipients, subject, bodyHtml, bodyText) {
      return osparc.store.Faker.getInstance().sendEmail(recipients, subject, bodyHtml, bodyText);
      const params = {
        data: {
          "channel": "email",
          "recipients": recipients,
          "content": {
            "subject": subject,
            "bodyHtml": bodyHtml,
            "bodyText": bodyText,
          },
        },
      };
      return osparc.data.Resources.fetch("sendMessage", "post", params);
    },
  }
});
