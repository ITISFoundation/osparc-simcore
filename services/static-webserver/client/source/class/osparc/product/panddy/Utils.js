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

qx.Class.define("osparc.product.panddy.Utils", {
  type: "static",

  statics: {
    STEPS: {
      "osparc": {
        getSteps: () => osparc.product.panddy.osparc.Sequence.getSteps()
      },
      "s4llite": {
        getSteps: () => osparc.product.panddy.osparc.Sequence.getSteps()
      }
    },

    hasPanddy: function() {
      const products = this.STEPS;
      const pName = osparc.product.Utils.getProductName();
      return Object.keys(products).includes(pName);
    },

    getSteps: function() {
      if (this.hasPanddy()) {
        const pName = osparc.product.Utils.getProductName();
        return this.STEPS[pName].getSteps();
      }
      return null;
    }
  }
});
