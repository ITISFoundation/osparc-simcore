/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget containing a Vertical Box with widgets.
 * Used for the side panel in the project editor.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let sidePanel = new qxapp.desktop.SidePanel();
 *   sidePanel.addAt(widget1, 0);
 *   sidePanel.addAt(widget2, 1);
 *   sidePanel.addAt(widget3, 2);
 *   this.getRoot().add(sidePanel);
 * </pre>
 */

qx.Class.define("qxapp.desktop.SidePanel", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments);

    this.setAppearance("sidepanel");

    this._setLayout(new qx.ui.layout.VBox());

    this.__attachEventHandlers();
  },

  properties: {
    collapsed: {
      init: false,
      check: "Boolean",
      apply: "_applyCollapsed"
    }
  },

  members: {
    __savedWidth: null,
    __collapsingDisabled: false,
    /**
     * Add a widget at the specified index. If the index already has a child, then replace it.
     *
     * @param {qx.ui.core.LayoutItem} child Widget to add
     * @param {Integer} index Index, at which the widget will be inserted
     * @param {Map?null} options Optional layout data for widget.
     */
    addOrReplaceAt: function(child, index, options = null) {
      if (this.getChildren()[index]) {
        this.removeAt(index);
      }
      this.addAt(child, index, options);
    },

    /**
     * Toggle the visibility of the side panel with a nice transition.
     */
    toggleCollapse: function() {
      this.setCollapsed(!this.getCollapsed());
    },

    _applyCollapsed: function(collapsed, old) {
      this.setDecorator("sidepanel");
      this.getChildren().forEach(child => child.setVisibility(collapsed ? "excluded" : "visible"));
      if (collapsed) {
        this.__savedWidth = this.getWidth();
        this.setWidth(20);
      } else {
        this.setWidth(this.__savedWidth);
      }
      // Workaround: have to update splitpane's prop
      this.getLayoutParent().__endSize = this.__savedWidth; // eslint-disable-line no-underscore-dangle
    },

    __attachEventHandlers: function() {
      this.addListenerOnce("appear", () => {
        this.getContentElement().getDomElement()
          .addEventListener("transitionend", () => {
            if (this.getCollapsed()) {
              this.addListenerOnce("resize", e => {
                if (this.getCollapsed() && this.getWidth() !== this.__savedWidth) {
                  this.__savedWidth = e.getData().width;
                  this.setCollapsed(false);
                } else {
                  this.__savedWidth = e.getData().width;
                }
              }, this);
            } else {
              this.resetDecorator();
            }
          });
      }, this);
    }
  }
});
