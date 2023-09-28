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

qx.Class.define("osparc.po.Overview", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const grid = new qx.ui.layout.Grid(20, 20);
    grid.setColumnFlex(0, 1);
    grid.setColumnFlex(1, 1);
    this._setLayout(grid);

    this.__buildLayout();
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        default:
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
    }
  }
});
