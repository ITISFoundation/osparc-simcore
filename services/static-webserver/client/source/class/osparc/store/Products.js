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

/**
 * @asset(osparc/ui_config.json")
 */

qx.Class.define("osparc.store.Products", {
  extend: qx.core.Object,
  type: "singleton",

  members: {
    __uiConfig: null,

    fetchUiConfig: function() {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          this.__uiConfig = {};
          resolve(this.__uiConfig);
        });
      }

      return osparc.utils.Utils.fetchJSON("/resource/osparc/ui_config.json")
        .then(uiConfig => {
          const product = osparc.product.Utils.getProductName()
          if (product in uiConfig) {
            this.__uiConfig = uiConfig[product];
          }
          return this.__uiConfig;
        })
        .catch(console.error);
    },

    getPlusButtonUiConfig: function() {
      return this.__uiConfig["plusButton"];
    },

    getNewStudiesUiConfig: function() {
      return this.__uiConfig["newStudies"];
    },
  }
});
