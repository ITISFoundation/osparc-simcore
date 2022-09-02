/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.StaticInfo", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    osparc.data.Resources.get("statics");
  },

  members: {
    getValue: function(key) {
      return new Promise((resolve, reject) => {
        osparc.data.Resources.get("statics")
          .then(staticData => {
            if (key in staticData) {
              resolve(staticData[key]);
            } else {
              const errorMsg = "key not found in statics";
              console.error(errorMsg);
              reject(errorMsg);
            }
          })
          .catch(err => reject(err));
      });
    },

    getDisplayNameKey: function() {
      const productName = osparc.utils.Utils.getProductName();
      return productName + "DisplayName";
    }
  }
});
