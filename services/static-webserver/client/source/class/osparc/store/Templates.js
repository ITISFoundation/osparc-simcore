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
  type: "static",

  statics: {
    __templatesCached: [],
    __templatesPromisesCached: null,

    fetchAllTemplates: function() {
      return this.__templatesPromisesCached = osparc.data.Resources.getInstance().getAllPages("templates")
        .then(templates => {
          this.__templates = templates;
          return templates;
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
        })
        .finally(() => {
          this.__templatesPromisesCached = null;
        });
    },

    getTemplates: function() {
      if (this.__templatesPromisesCached) {
        return this.__templatesPromisesCached;
      }

      return new Promise(resolve => resolve(this.__templates));
    },

    getTemplatesHypertools: function() {
      return this.getTemplates()
        .then(templates => {
          return templates.filter(t => osparc.study.Utils.extractTemplateType(t) === osparc.data.model.StudyUI.HYPERTOOL_TYPE);
        });
    },

    getTemplate: function(templateId) {
      return this.getTemplates()
        .then(templates => {
          return templates.find(t => t.uuid === templateId);
        });
    },
  }
});
