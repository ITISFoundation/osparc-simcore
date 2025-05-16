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

    __fetchTemplatesPaginated: function(params, options) {
      params["url"]["templateType"] = osparc.data.model.StudyUI.TEMPLATE_TYPE;
      return osparc.data.Resources.fetch("templates", "getPageFilteredSorted", params, options)
        .then(response => {
          const templates = response["data"];
          templates.forEach(template => template["resourceType"] = "template");
          return response;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    fetchTemplatesNonPublicPaginated: function(params, options) {
      return this.__fetchTemplatesPaginated(params, options);
    },

    fetchTemplatesPublicPaginated: function(params, options) {
      return this.__fetchTemplatesPaginated(params, options);
    },

    __fetchAllTutorials: function(params) {
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

    __fetchAllHypertools: function(params) {
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
      const params = {
        url: {
          "orderBy": JSON.stringify({
            field: "last_change_date",
            direction: "desc"
          }),
        }
      };

      if (this.__tutorialsPromiseCached) {
        return this.__tutorialsPromiseCached;
      }

      if (this.__tutorials === null) {
        // no tutorials cached, fetch them
        return this.__fetchAllTutorials(params);
      }

      if (useCache) {
        // tutorials already cached, return them
        return new Promise(resolve => resolve(this.__tutorials));
      }

      return this.__fetchAllTutorials(params);
    },

    getHypertools: function(useCache = true) {
      const params = {
        url: {
          "orderBy": JSON.stringify({
            field: "last_change_date",
            direction: "desc"
          }),
        }
      };

      if (this.__hypertoolsPromiseCached) {
        return this.__hypertoolsPromiseCached;
      }

      if (this.__hypertools === null) {
        // no hypertools cached, fetch them
        return this.__fetchAllHypertools(params);
      }

      if (useCache) {
        // hypertools already cached, return them
        return new Promise(resolve => resolve(this.__hypertools));
      }

      return this.__fetchAllHypertools(params);
    },
  }
});
