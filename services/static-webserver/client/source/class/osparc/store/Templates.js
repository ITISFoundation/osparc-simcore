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
    __templates: null,
    __templatesPromisesCached: null,

    __fetchAllTemplates: function() {
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

    getTemplates: function(useCache = true) {
      if (this.__templatesPromisesCached) {
        // fetching templates already in progress
        return this.__templatesPromisesCached;
      }

      if (this.__templates === null) {
        // no templates cached, fetch them
        return this.__fetchAllTemplates();
      }

      if (useCache) {
        // templates already cached, return them
        return new Promise(resolve => resolve(this.__templates));
      }
      // templates cached but force a refresh
      return this.__fetchAllTemplates();
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
