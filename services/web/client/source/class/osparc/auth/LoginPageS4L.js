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
      layout.setRowFlex(1, 1);
      this._setLayout(layout);

      this.setBackgroundColor("#025887");
      this.getContentElement().setStyles({
        "background-image": "url(resource/osparc/s4l_splitimage.jpeg)",
        "background-repeat": "no-repeat",
        "background-size": "auto 100%"
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
