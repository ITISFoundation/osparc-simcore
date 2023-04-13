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
    SEQUENCES: {
      "s4llite": {
        getSequences: () => osparc.product.panddy.s4llite.Sequences.getSequences()
      }
    },

    hasPanddy: function() {
      if (osparc.utils.Utils.isDevelEnv()) {
        const sequences = this.SEQUENCES;
        const pName = osparc.product.Utils.getProductName();
        return Object.keys(sequences).includes(pName);
      }
      return false;
    },

    getSequences: function() {
      if (this.hasPanddy()) {
        const pName = osparc.product.Utils.getProductName();
        return this.SEQUENCES[pName].getSequences();
      }
      return null;
    }
  }
});
