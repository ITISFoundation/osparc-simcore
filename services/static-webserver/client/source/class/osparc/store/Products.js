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

qx.Class.define("osparc.store.Products", {
  extend: qx.core.Object,
  type: "singleton",

  members: {
    __plusButtonUiConfig: null,

    fetchPlusButtonUiConfig: function() {
      return osparc.utils.Utils.fetchJSON("/resource/osparc/ui_config.json")
        .then(newStudiesData => {
          const product = osparc.product.Utils.getProductName()
          if (product in newStudiesData) {
            this.__plusButtonUiConfig = newStudiesData[product];
            return this.__plusButtonUiConfig;
          }
          return {};
        })
        .catch(console.error);
    },

    getPlusButtonUiConfig: function() {
      return new Promise(resolve => {
        if (this.__plusButtonUiConfig) {
          resolve(this.__plusButtonUiConfig);
        } else {
          resolve(this.fetchPlusButtonUiConfig())
        }
      });
    },
  }
});
