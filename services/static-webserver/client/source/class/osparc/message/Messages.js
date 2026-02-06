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
      return osparc.data.Resources.fetch("notificationTemplates", "searchEmailTemplates")
        .then(templates => {
          return templates.filter(t => t.ref.templateName === "empty");
        });
    },

    fetchEmailPreview: function(templateName, context = {}) {
      const params = {
        data: {
          "ref": {
            "channel": "email",
            "templateName": templateName,
          },
          "context": context,
        },
      };
      return osparc.data.Resources.fetch("notificationTemplates", "previewTemplate", params)
    },

    sendMessage: function(group_ids, subject, bodyHtml, bodyText) {
      const params = {
        data: {
          "channel": "email",
          "group_ids": group_ids,
          "content": {
            "subject": subject,
            "bodyHtml": bodyHtml,
            "bodyText": bodyText,
          },
        },
      };
      return osparc.data.Resources.fetch("notificationTemplates", "sendMessage", params);
    },
  }
});
