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

    const padding = osparc.dashboard.Dashboard.PADDING;
    const leftColumnWidth = this.self().SIDE_SPACER_WIDTH;
    const emptyColumnMinWidth = 50;
    const spacing = 20;
    const mainLayoutsScroll = 8;

    this.__mainLayoutWithSides = new qx.ui.container.Composite(new qx.ui.layout.HBox(spacing))
    stack.add(this.__mainLayoutWithSides);

    this.__leftColum = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
      width: leftColumnWidth
    });
    this.__mainLayoutWithSides.add(this.__leftColum);

    this._mainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this.__mainLayoutWithSides.add(this._mainLayout);

    const rightColum = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this.__mainLayoutWithSides.add(rightColum, {
      flex: 1
    });

    const itemWidth = osparc.dashboard.GridButtonBase.ITEM_WIDTH + osparc.dashboard.GridButtonBase.SPACING;
    this._mainLayout.setMinWidth(this.self().MIN_STUDIES_PER_ROW * itemWidth + mainLayoutsScroll);
    const fitResourceCards = () => {
      const w = document.documentElement.clientWidth;
      const nStudies = Math.floor((w - 2*padding - 2*spacing - leftColumnWidth - emptyColumnMinWidth) / itemWidth);
      const newWidth = nStudies * itemWidth + 8;
      if (newWidth > this._mainLayout.getMinWidth()) {
        this._mainLayout.setWidth(newWidth);
      } else {
        this._mainLayout.setWidth(this._mainLayout.getMinWidth());
      }

      const compactVersion = w < this._mainLayout.getMinWidth() + leftColumnWidth + emptyColumnMinWidth;
      this.__leftColum.setVisibility(compactVersion ? "excluded" : "visible");
      rightColum.setVisibility(compactVersion ? "excluded" : "visible");
    };
    fitResourceCards();
    window.addEventListener("resize", () => fitResourceCards());
  },

  statics: {
    MIN_STUDIES_PER_ROW: 4,
    SIDE_SPACER_WIDTH: 180
  },

  members: {
    __stack: null,
    _loadingPage: null,
    __mainLayoutWithSides: null,
    __leftColum: null,
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

    _addToLeftColumn: function(widget, props = {}) {
      this.__leftColum.add(widget, props);
    },

    _addToMainLayout: function(widget, props = {}) {
      this._mainLayout.add(widget, props);
    }
  }
});
