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
    __tutorials: null,
    __tutorialsPromiseCached: null,
    __hypertools: null,
    __hypertoolsPromiseCached: null,

    createTemplate: function(studyId, copyData = true, hidden = false) {
      const params = {
        url: {
          "study_id": studyId,
          "copy_data": copyData,
          hidden,
        },
      };
      const options = {
        pollTask: true
      };
      return osparc.data.Resources.fetch("studies", "postToTemplate", params, options);
    },

    fetchTemplatesPaginated: function(params, options) {
      params["url"]["templateType"] = osparc.data.model.StudyUI.TEMPLATE_TYPE;
      return osparc.data.Resources.fetch("templates", "getPageFilteredSorted", params, options)
        .then(response => {
          const templates = response["data"];
          templates.forEach(template => template["resourceType"] = "template");
          return response;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    searchTemplatesPaginated: function(params, options) {
      params["url"]["templateType"] = osparc.data.model.StudyUI.TEMPLATE_TYPE;
      return osparc.data.Resources.fetch("templates", "getPageSearchFilteredSorted", params, options)
        .then(response => {
          const templates = response["data"];
          templates.forEach(template => template["resourceType"] = "template");
          return response;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    fetchTemplate: function(templateId) {
      return osparc.store.Study.getInstance().getOne(templateId)
        .catch(err => console.error(err));
    },

    __fetchAllTutorials: function() {
      const params = {
        url: {
          "orderBy": JSON.stringify({
            field: "last_change_date",
            direction: "desc"
          }),
        }
      };
      params["url"]["templateType"] = osparc.data.model.StudyUI.TUTORIAL_TYPE;
      return this.__tutorialsPromiseCached = osparc.data.Resources.getInstance().getAllPages("templates", params, "getPageFilteredSorted")
        .then(tutorials => {
          tutorials.forEach(tutorial => tutorial["resourceType"] = "tutorial");
          this.__tutorials = tutorials;
          return tutorials;
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
        })
        .finally(() => {
          this.__tutorialsPromiseCached = null;
        });
    },

    __fetchAllHypertools: function() {
      const params = {
        url: {
          "orderBy": JSON.stringify({
            field: "last_change_date",
            direction: "desc"
          }),
        }
      };
      params["url"]["templateType"] = osparc.data.model.StudyUI.HYPERTOOL_TYPE;
      return this.__hypertoolsPromiseCached = osparc.data.Resources.getInstance().getAllPages("templates", params, "getPageFilteredSorted")
        .then(hypertools => {
          hypertools.forEach(hypertool => hypertool["resourceType"] = "hypertool");
          this.__hypertools = hypertools;
          return hypertools;
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
        })
        .finally(() => {
          this.__hypertoolsPromiseCached = null;
        });
    },

    getTutorials: function(useCache = true) {
      if (this.__tutorialsPromiseCached) {
        return this.__tutorialsPromiseCached;
      }

      if (this.__tutorials === null) {
        // no tutorials cached, fetch them
        return this.__fetchAllTutorials();
      }

      if (useCache) {
        // tutorials already cached, return them
        return new Promise(resolve => resolve(this.__tutorials));
      }

      return this.__fetchAllTutorials();
    },

    getHypertools: function(useCache = true) {
      if (this.__hypertoolsPromiseCached) {
        return this.__hypertoolsPromiseCached;
      }

      if (this.__hypertools === null) {
        // no hypertools cached, fetch them
        return this.__fetchAllHypertools();
      }

      if (useCache) {
        // hypertools already cached, return them
        return new Promise(resolve => resolve(this.__hypertools));
      }

      return this.__fetchAllHypertools();
    },

    getTemplate: function(templateId) {
      if (this.__tutorials) {
        const template = this.__tutorials.find(t => t["templateId"] === templateId);
        if (template) {
          return new osparc.data.model.Template(template);
        }
      } else if (this.__hypertools) {
        const template = this.__hypertools.find(t => t["templateId"] === templateId);
        if (template) {
          return new osparc.data.model.Template(template);
        }
      }
      return null;
    },
  }
});
