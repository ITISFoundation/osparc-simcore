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
    getInaccessibleServicesMsg: function(inaccessibleServices) {
      let msg = qx.locale.Manager.tr("Service(s) not accessible:<br>");
      inaccessibleServices.forEach(unaccessibleService => {
        msg += `- ${unaccessibleService.label}:${unaccessibleService.version}<br>`;
      });
      return msg;
    },

    mustache: {
      mustacheRegEx: function() {
        return /{{([^{}]*)}}/g;
      },

      mustache2Var: function(mustached) {
        return mustached.replace("{{", "").replace("}}", "");
      },

      getVariables: function(obj) {
        const variables = new Set();
        const secondaryStudyDataStr = JSON.stringify(obj);
        const mustaches = secondaryStudyDataStr.match(this.self().mustache.mustacheRegEx()) || [];
        mustaches.forEach(mustache => {
          const variable = this.self().mustache.mustache2Var(mustache);
          variables.add(variable);
        });
        return Array.from(variables);
      }
    }
  }
});
