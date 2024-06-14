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

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    const stack = this.__stack = new qx.ui.container.Stack();
    this._add(stack, {
      flex: 1
    });

    this._loadingPage = new osparc.ui.message.Loading();
    stack.add(this._loadingPage);

    this.__mainLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox())
    stack.add(this.__mainLayout);
  },

  members: {
    __stack: null,
    _loadingPage: null,
    __mainLayout: null,

    _showLoadingPage: function(label) {
      if (label) {
        this._loadingPage.setHeader(label);
      }
      this.__stack.setSelection([this._loadingPage]);
    },

    _showMainLayout: function() {
      this.__stack.setSelection([this.__mainLayout]);
    },

    _hideLoadingPage: function() {
      this._showMainLayout();
    },

    _addToMainLayout: function(widget, props = {}) {
      this.__mainLayout.add(widget, props);
    }
  }
});
