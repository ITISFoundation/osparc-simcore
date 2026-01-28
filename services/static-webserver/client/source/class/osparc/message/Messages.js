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
      return osparc.data.Resources.fetch("notifications", "searchEmailTemplates");
    },

    fetchEmailPreview: function(templateName, context = {}) {
      const params = {
        data: {
          "ref": {
            "channel": "email",
            "templateName": templateName,
          },
          "context": context
        }
      };
      return osparc.data.Resources.fetch("notifications", "previewTemplate", params)
    },

    sendMessage: function(recipients, subject, bodyHtml, bodyText) {
      const params = {
        data: {
          "channel": "email",
          "recipients": recipients,
          "content": {
            "subject": subject,
            "bodyHtml": bodyHtml,
            "bodyText": bodyText,
          }
        }
      };
      return osparc.data.Resources.fetch("notifications", "sendMessage", params);
    },
  }
});
