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

    this.__templates = [];
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
      return osparc.store.Faker.getInstance().fetchEmailTemplates()
      // return osparc.data.Resources.fetch("notificationTemplates", "getTemplates")
        .then(templates => {
          Object.keys(templates).forEach(templateId => {
            const templateData = templates[templateId];
            templateData["id"] = templateId;
            this.__addTemplate(templateData);
          });
          return this.__templates;
        });
    },

    getTemplates: function() {
      return this.__templates;
    },

    getTemplate: function(templateId) {
      return this.__templates.find(template => template.id === templateId);
    },

    __addTemplate: function(templateData) {
      this.__templates.push(templateData);
      this.__templates.sort((a, b) => new Date(b.getDate()) - new Date(a.getDate()));
    },
  }
});
