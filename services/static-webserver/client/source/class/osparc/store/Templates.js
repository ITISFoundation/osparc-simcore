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

qx.Class.define("osparc.store.Templates", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.__templates = [];
  },

  members: {
    __templates: null,

    fetchAllTemplates: function() {
      if (this.__templates.length) {
        return new Promise(resolve => resolve(this.__templates));
      }

      return osparc.data.Resources.getInstance().getAllPages("templates")
        .then(templates => {
          this.__templates = templates;
          return templates;
        });
    },

    getTemplates: function() {
      return this.__templates;
    },

    getTemplatesByType: function(type) {
      return this.__templates.filter(t => osparc.study.Utils.extractTemplateType(t) === type);
    },

    getTemplate: function(templateId) {
      return this.__templates.find(t => t.uuid === templateId);
    },
  }
});
