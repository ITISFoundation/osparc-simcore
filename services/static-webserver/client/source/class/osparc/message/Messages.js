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
    fetchEmailEmptyTemplate: function() {
      const params = {
        url: {
          "templateName": "empty",
        },
      };
      return osparc.data.Resources.fetch("notificationTemplates", "searchEmailTemplates", params);
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
      return osparc.data.Resources.fetch("notificationTemplates", "previewTemplate", params);
    },

    sendMessage: function(groupIds, subject, bodyHtml, bodyText) {
      const params = {
        data: {
          "channel": "email",
          "groupIds": groupIds,
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
