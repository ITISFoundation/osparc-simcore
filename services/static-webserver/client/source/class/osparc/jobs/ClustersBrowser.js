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


qx.Class.define("osparc.jobs.ClustersBrowser", {
  extend: qx.ui.core.Widget,

  construct() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.getChildControl("clusters-table");
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "clusters-table":
          control = new osparc.jobs.ClustersTable();
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },
  }
})
