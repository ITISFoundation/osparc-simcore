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

/**
 * @asset(osparc/tours/s4llite_tours.json)
 * @asset(osparc/tours/s4l_tours.json)
 * @asset(osparc/tours/tis_tours.json)
 */

qx.Class.define("osparc.product.tours.Tours", {
  type: "static",

  statics: {
    TOURS: {
      "s4llite": {
        fetchTours: () => osparc.product.tours.Tours.fetchTours("/resource/osparc/tours/s4llite_tours.json")
      },
      "s4l": {
        fetchTours: () => osparc.product.tours.Tours.fetchTours("/resource/osparc/tours/s4l_tours.json")
      },
      "s4lacad": {
        fetchTours: () => osparc.product.tours.Tours.fetchTours("/resource/osparc/tours/s4l_tours.json")
      },
      "tis": {
        fetchTours: () => osparc.product.tours.Tours.fetchTours("/resource/osparc/tours/tis_tours.json")
      },
      "tiplite": {
        fetchTours: () => osparc.product.tours.Tours.fetchTours("/resource/osparc/tours/tiplite_tours.json")
      },
    },

    fetchTours: function(link) {
      return osparc.utils.Utils.fetchJSON(link)
        .then(Object.values)
        .catch(console.error);
    },

    // it returns a promise
    getTours: function() {
      const pName = osparc.product.Utils.getProductName();
      if (Object.keys(this.TOURS).includes(pName)) {
        return this.TOURS[pName].fetchTours();
      }
      return null;
    }
  }
});
