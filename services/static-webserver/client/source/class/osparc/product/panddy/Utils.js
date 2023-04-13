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
      "osparc": {
        getSequences: () => osparc.product.panddy.osparc.Sequences.getSequences()
      },
      "s4llite": {
        getSequences: () => osparc.product.panddy.osparc.Sequences.getSequences()
      }
    },

    hasPanddy: function() {
      const sequences = this.SEQUENCES;
      const pName = osparc.product.Utils.getProductName();
      return Object.keys(sequences).includes(pName);
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
