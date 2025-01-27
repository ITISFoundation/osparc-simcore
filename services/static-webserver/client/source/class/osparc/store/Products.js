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
    __newStudyConfig: null,

    fetchNewStudyConfig: function() {
      return osparc.utils.Utils.fetchJSON("/resource/osparc/new_studies.json")
        .then(newStudiesData => {
          const product = osparc.product.Utils.getProductName()
          if (product in newStudiesData) {
            this.__newStudyConfig = newStudiesData[product];
            return this.__newStudyConfig;
          }
          return {};
        })
        .catch(console.error);
    },

    getNewStudyConfig: function() {
      return new Promise(resolve => {
        if (this.__newStudyConfig) {
          resolve(this.__newStudyConfig);
        } else {
          resolve(this.fetchNewStudyConfig())
        }
      });
    },
  }
});
