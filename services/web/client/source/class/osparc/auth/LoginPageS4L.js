/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 *  Main Authentication Page:
 *    A multi-page view that fills all page
 */

qx.Class.define("osparc.auth.LoginPageS4L", {
  extend: osparc.auth.LoginPage,

  /*
  *****************************************************************************
     CONSTRUCTOR
  *****************************************************************************
  */
  construct: function() {
    this.base(arguments);
  },

  events: {
    "done": "qx.event.type.Data"
  },

  members: {
    // overriden
    _buildLayout: function() {
      const layout = new qx.ui.layout.Grid(20, 20);
      layout.setColumnMaxWidth(0, 800);
      layout.setRowFlex(1, 1);
      this._setLayout(layout);

      this.setBackgroundColor("#025887");

      const image = new osparc.ui.basic.Thumbnail("osparc/s4l_splitimage.jpeg");
      this._add(image, {
        row: 0,
        column: 0,
        rowSpan: 2
      });

      const pages = this._getLoginStack();
      this._add(pages, {
        row: 0,
        column: 1
      });

      const versionLink = this._getVersionLink();
      this._add(versionLink, {
        row: 1,
        column: 1
      });
    }
  }
});
