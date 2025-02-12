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
        .then(uiConfig => {
          const product = osparc.product.Utils.getProductName()
          if (product in uiConfig && "plusButton" in uiConfig[product]) {
            this.__plusButtonUiConfig = uiConfig[product]["plusButton"];
          } else {
            this.__plusButtonUiConfig = false;
          }
          return this.__plusButtonUiConfig;
        })
        .catch(console.error);
    },

    getPlusButtonUiConfig: function() {
      return this.__plusButtonUiConfig;
    },
  }
});
