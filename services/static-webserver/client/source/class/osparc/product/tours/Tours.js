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
        fetchTours: () => this.__fetchTours("/resource/osparc/tours/s4llite_tours.json")
      },
      "s4l": {
        fetchTours: () => this.__fetchTours("/resource/osparc/tours/s4l_tours.json")
      },
      "tis": {
        fetchTours: () => this.__fetchTours("/resource/osparc/tours/tis_tours.json")
      }
    },

    __fetchTours: function(link) {
      return new Promise((resolve, reject) => {
        osparc.utils.Utils.fetchJSON(link)
          .then(toursObj => {
            const tours = Object.values(toursObj);
            resolve(tours);
          })
          .catch(err => {
            console.error(err);
            reject();
          });
      });
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
