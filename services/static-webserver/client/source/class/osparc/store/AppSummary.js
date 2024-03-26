/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.AppSummary", {
  type: "static",

  statics: {
    getLatestUIFromBE: async function() {
      const params = {
        url: {
          productName: osparc.product.Utils.getProductName()
        }
      };
      const appSummary = await osparc.data.Resources.fetch("appSummary", "get", params);
      if (appSummary && "environment" in appSummary && "osparc.vcsRefClient" in appSummary["environment"]) {
        return appSummary["environment"]["osparc.vcsRefClient"];
      }
      return null;
    }
  }
});
