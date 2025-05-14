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

    fetchTemplatesPaginated: function(params, options) {
      return osparc.data.Resources.fetch("templates", "getPage", params, options)
        .then(resp => {
          const templates = resp.data;
          // add them to the list
          if (this.__templates) {
            templates.forEach(template => {
              const index = this.__templates.findIndex(t => t.uuid === template.uuid);
              if (index === -1) {
                this.__templates.push(template);
              } else {
                this.__templates[index] = template;
              }
            });
          }
          return resp;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

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
          const hypertools = templates.filter(t => osparc.study.Utils.extractTemplateType(t) === osparc.data.model.StudyUI.HYPERTOOL_TYPE);
          // required for filtering
          hypertools.forEach(hypertool => hypertool.type = osparc.data.model.StudyUI.HYPERTOOL_TYPE);
          return hypertools;
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
