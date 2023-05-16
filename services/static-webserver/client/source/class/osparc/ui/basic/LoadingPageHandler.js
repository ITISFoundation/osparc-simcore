/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Abstract widget that handles the loading page + main widget
 */
qx.Class.define("osparc.ui.basic.LoadingPageHandler", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  members: {
    _loadingPage: null,

    _showLoadingPage: function(label) {
      this._hideLoadingPage();

      this._showMainLayout(false);

      if (this._loadingPage === null) {
        this._loadingPage = new osparc.ui.message.Loading();
      }
      this._loadingPage.setHeader(label);
      this._add(this._loadingPage, {
        flex: 1
      });
    },

    _hideLoadingPage: function() {
      if (this._loadingPage) {
        const idx = this._indexOf(this._loadingPage);
        if (idx !== -1) {
          this._remove(this._loadingPage);
        }
      }

      this._showMainLayout(true);
    },

    /**
     * @abstract
     */
    _showMainLayout: function() {
      throw new Error("Abstract method called!");
    }
  }
});
