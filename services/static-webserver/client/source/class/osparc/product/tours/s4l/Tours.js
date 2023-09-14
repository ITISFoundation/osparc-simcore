/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @asset(osparc/tours/s4l_tours.json)
 */

qx.Class.define("osparc.product.tours.s4l.Tours", {
  type: "static",

  statics: {
    fetchTours: function() {
      return new Promise((resolve, reject) => {
        osparc.utils.Utils.fetchJSON("/resource/osparc/tours/s4l_tours.json")
          .then(toursObj => {
            const tours = Object.values(toursObj);
            console.log("tours", tours);
            resolve(tours);
          })
          .catch(err => {
            console.error(err);
            reject();
          });
      });
    }
  }
});
