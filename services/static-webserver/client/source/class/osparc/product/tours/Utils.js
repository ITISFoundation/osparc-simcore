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
        fetchTours: () => osparc.product.tours.s4llite.Tours.fetchTours()
      },
      "s4l": {
        fetchTours: () => osparc.product.tours.s4l.Tours.fetchTours()
      }
    },

    // it returns a promise
    getTours: function() {
      if (osparc.utils.Utils.isDevelEnv()) {
        const pName = osparc.product.Utils.getProductName();
        if (Object.keys(this.TOURS).includes(pName)) {
          return this.TOURS[pName].fetchTours();
        }
      }
      return null;
    }
  }
});
