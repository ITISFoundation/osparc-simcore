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

    this.__mainLayoutWithSides = new qx.ui.container.Composite(new qx.ui.layout.HBox(5))
    stack.add(this.__mainLayoutWithSides);

    const leftSpace = new qx.ui.core.Widget();
    this.__mainLayoutWithSides.add(leftSpace, {
      flex: 1
    });

    this._mainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this.__mainLayoutWithSides.add(this._mainLayout);

    const rightSpace = new qx.ui.core.Widget();
    this.__mainLayoutWithSides.add(rightSpace, {
      flex: 1
    });

    const itemWidth = osparc.dashboard.GridButtonBase.ITEM_WIDTH + osparc.dashboard.GridButtonBase.SPACING;
    const sideMaxWidth = 150;
    this._mainLayout.setMinWidth(this.self().MIN_STUDIES_PER_ROW * itemWidth + 8);
    const fitResourceCards = () => {
      const w = document.documentElement.clientWidth;
      const nStudies = Math.floor((w - 2*sideMaxWidth - 8) / itemWidth);
      const newWidth = nStudies * itemWidth + 8;
      if (newWidth > this._mainLayout.getMinWidth()) {
        this._mainLayout.setMaxWidth(newWidth);
      } else {
        this._mainLayout.setMaxWidth(this._mainLayout.getMinWidth());
      }
    };
    fitResourceCards();
    window.addEventListener("resize", () => fitResourceCards());
  },

  statics: {
    MIN_STUDIES_PER_ROW: 4
  },

  members: {
    __stack: null,
    _loadingPage: null,
    __mainLayoutWithSides: null,
    _mainLayout: null,

    _showLoadingPage: function(label) {
      if (label) {
        this._loadingPage.setHeader(label);
      }
      this.__stack.setSelection([this._loadingPage]);
    },

    _showMainLayout: function() {
      this.__stack.setSelection([this.__mainLayoutWithSides]);
    },

    _hideLoadingPage: function() {
      this._showMainLayout();
    },

    _addToMainLayout: function(widget, props = {}) {
      this._mainLayout.add(widget, props);
    }
  }
});
