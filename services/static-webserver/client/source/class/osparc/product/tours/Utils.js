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

qx.Class.define("osparc.product.tours.Utils", {
  type: "static",

  statics: {
    TOURS: {
      "s4llite": {
        getTours: () => osparc.product.tours.s4llite.Tours.getTours()
      },
      "s4l": {
        getTours: () => osparc.product.tours.s4l.Tours.getTours()
      }
    },

    hasTours: function() {
      if (osparc.utils.Utils.isDevelEnv()) {
        const tours = this.TOURS;
        const pName = osparc.product.Utils.getProductName();
        return Object.keys(tours).includes(pName);
      }
      return false;
    },

    getTours: function() {
      if (this.hasTours()) {
        const pName = osparc.product.Utils.getProductName();
        return this.TOURS[pName].getTours();
      }
      return null;
    }
  }
});
