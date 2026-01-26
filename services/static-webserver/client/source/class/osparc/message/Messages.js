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
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__templates = new qx.data.Array();
  },

  statics: {
    getTemplatePreview: function(type, data) {
      const params = {
        type,
        data,
      };
      return osparc.data.Resources.fetch("getTemplatePreview", "post", params);
    },

    sendMessageFromTemplate: function(data) {
      const params = {
        data,
      };
      return osparc.data.Resources.fetch("sendMessageFromTemplate", "post", params);
    },

    sendMessage: function(data) {
      console.log("Faker sending email with data:", data);
      return new Promise((resolve) => resolve());
      const params = {
        data,
      };
      return osparc.data.Resources.fetch("sendMessage", "post", params);
    },
  },

  members: {
    __templates: null,

    fetchTemplates: function() {
      return osparc.data.Resources.fetch("notificationTemplates", "getTemplates")
        .then(templates => {
          templates.forEach(template => {
            this.__addTemplate(template);
          });
          return this.__templates;
        });
    },

    getTemplates: function() {
      return this.__templates;
    },

    __addTemplate: function(templateData) {
      this.__templates.push(templateData);
      this.__templates.sort((a, b) => new Date(b.getDate()) - new Date(a.getDate()));
    },
  }
});
