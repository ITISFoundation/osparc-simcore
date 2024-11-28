/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.vipStore.AnatomicalModelDetails", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid(10, 10);
    layout.setColumnWidth(0, 64);
    layout.setRowFlex(0, 1);
    layout.setColumnFlex(1, 1);
    layout.setColumnAlign(0, "center", "middle");
    layout.setColumnAlign(1, "left", "middle");
    this._setLayout(layout);

    this.set({
      padding: 5,
    });
  },

  properties: {
    anatomicalModelsData: {
      check: "String",
      init: null,
      nullable: false,
      apply: "__poplulateLayout"
    },
  },

  members: {

    __poplulateLayout: function() {
      this.getChildControl("thumbnail").setSource(value);
    },
  }
});
