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
 * @asset(osaprc/s4l_tours.json)
 */

qx.Class.define("osparc.product.panddy.s4l.Tours", {
  extend: qx.ui.core.Widget,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.set({
      zIndex: 100000
    });

    osparc.utils.Utils.fetchJSON("/resource/osparc/s4l_tours.json")
      .then(tours => {
        console.log("tours", tours);
        this.setTours(tours);
      });
  },

  properties: {
    tours: {
      check: "Array",
      init: [],
      nullable: true
    }
  }
});
