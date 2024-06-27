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

/**
 * Grid layout that shows an element well centered
 *  ___________________________________
 * |flex Spacer|flex Spacer|flex Spacer|
 * |flex Spacer|  element  |flex Spacer|
 * |flex Spacer|flex Spacer|flex Spacer|
 */
qx.Class.define("osparc.ui.layout.CenteredGrid", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid();
    layout.setRowFlex(0, 1);
    layout.setRowFlex(2, 1);
    layout.setColumnFlex(0, 1);
    layout.setColumnFlex(2, 1);
    this._setLayout(layout);

    [
      [0, 0],
      [0, 1],
      [0, 2],
      [1, 0],
      [1, 2],
      [2, 0],
      [2, 1],
      [2, 2]
    ].forEach(quad => {
      const empty = new qx.ui.core.Spacer();
      this._add(empty, {
        row: quad[0],
        column: quad[1]
      });
    });
  },

  members: {
    addCenteredWidget: function(widget) {
      this._add(widget, {
        row: 1,
        column: 1
      });
    }
  }
});
