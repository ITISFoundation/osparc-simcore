/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Collection of methods for studies
 */

qx.Class.define("osparc.utils.Study", {
  type: "static",

  statics: {
    getInaccessibleServicesMsg: function(unaccessibleServices) {
      let msg = this.tr("Service(s) not accessible:<br>");
      unaccessibleServices.forEach(unaccessibleService => {
        msg += `- ${unaccessibleService.label}:${unaccessibleService.version}<br>`;
      });
      return msg;
    },

    mustache: {
      mustacheRegEx: function() {
        return /{{([^{}]*)}}/g;
      },

      getVariables: function(obj) {
        const variables = new Set();
        const secondaryStudyDataStr = JSON.stringify(obj);
        const mustaches = secondaryStudyDataStr.match(this.mustache.mustacheRegEx()) || [];
        mustaches.forEach(mustache => {
          const variable = mustache.replace("{{", "").replace("}}", "");
          variables.add(variable);
        });
        return Array.from(variables);
      },

      replace: function(obj, parameters) {
        const mustaches = this.mustache.getVariables(obj);
        let objStr = JSON.stringify(obj);
        mustaches.forEach(mustache => {
          const paramId = mustache.replace("{{", "").replace("}}", "");
          const parameter = parameters.find(param => param.id === paramId);
          if (parameter) {
            objStr = objStr.replace(mustache, parameter.label);
          }
        });
        return JSON.parse(objStr);
      }
    }
  }
});
