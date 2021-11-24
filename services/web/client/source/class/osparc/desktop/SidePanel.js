/* ************************************************************************

   osparc - the simcore frontend

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
 * Used for the side panel in the study editor.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let sidePanel = new osparc.desktop.SidePanel();
 *   sidePanel.addAt(widget1, 0);
 *   sidePanel.addAt(widget2, 1);
 *   sidePanel.addAt(widget3, 2);
 *   this.getRoot().add(sidePanel);
 * </pre>
 */

qx.Class.define("osparc.desktop.SidePanel", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments);

    this.setAppearance("sidepanel");

    this._setLayout(new qx.ui.layout.VBox(null, null, "separator-vertical"));

    this.__attachEventHandlers();
  },

  properties: {
    collapsed: {
      init: false,
      check: "Boolean",
      event: "changeCollapsed",
      apply: "_applyCollapsed"
    },

    collapsedView: {
      init: null,
      check: "qx.ui.core.Widget"
    },

    collapsedMinWidth: {
      check: "Number",
      init: 0
    },

    collapsedWidth: {
      check: "Number",
      init: 20
    }
  },

  members: {
    __savedWidth: null,
    __savedMinWidth: null,
    /**
     * Add a widget at the specified index. If the index already has a child, then replace it.
     *
     * @param {qx.ui.core.LayoutItem} child Widget to add
     * @param {Integer} index Index, at which the widget will be inserted
     * @param {Map?null} options Optional layout data for widget.
     */
    addOrReplaceAt: function(child, index, options = null) {
      if (this.getChildren()[index]) {
        const visibility = this.getChildren()[index].getVisibility();
        child.setVisibility(visibility);
        this.removeAt(index);
      }
      this.addAt(child, index, options);
    },

    /**
     * Toggle the visibility of the side panel with a nice transition.
     */
    toggleCollapsed: function() {
      this.setCollapsed(!this.getCollapsed());
    },

    _applyCollapsed: function(collapsed) {
      this.__setDecorators("sidepanel");

      this.getChildren().forEach(child => child.setVisibility(collapsed ? "excluded" : "visible"));
      if (this.getCollapsedView() !== null) {
        if (collapsed) {
          this.add(this.getCollapsedView(), {
            flex: 1
          });
        } else {
          this.remove(this.getCollapsedView());
        }
      }

      const splitpaneContainer = this.__getSplitpaneContainer();
      if (collapsed) {
        // Save widths
        this.__savedWidth = this.__getCssWidth();
        this.__savedMinWidth = splitpaneContainer.getMinWidth();
        splitpaneContainer.set({
          minWidth: this.getCollapsedMinWidth(),
          width: this.getCollapsedWidth()
        });
      } else {
        // Restore widths
        splitpaneContainer.set({
          minWidth: this.__savedMinWidth,
          width: this.__savedWidth
        });
      }
      // Workaround: have to update splitpane's prop
      const splitpane = this.__getParentSplitpane();
      if (splitpane && this.__savedWidth) {
        splitpane.__endSize = this.__savedWidth; // eslint-disable-line no-underscore-dangle
      }
    },

    __getParentSplitpane: function() {
      let parent = this.getLayoutParent();
      while (parent && parent instanceof qx.ui.splitpane.Pane === false) {
        parent = parent.getLayoutParent();
      }
      return parent;
    },

    __getSplitpaneContainer: function() {
      const splitpane = this.__getParentSplitpane();
      if (splitpane == null) {
        return this;
      }
      let container = this;
      while (container.getLayoutParent() !== splitpane) {
        container = container.getLayoutParent();
      }
      return container;
    },

    __getCssWidth: function() {
      if (this.__getSplitpaneContainer().getWidth()) {
        return this.__getSplitpaneContainer().getWidth();
      } else if (this.__getSplitpaneContainer().getContentElement()
        .getDomElement()) {
        return parseInt(this.__getSplitpaneContainer().getContentElement()
          .getDomElement().style.width);
      }
      return 300;
    },

    __setDecorators: function(decorator = null) {
      const splitpane = this.__getParentSplitpane() || this;
      let widget = this;
      do {
        if (decorator) {
          widget.setDecorator(decorator);
        } else {
          widget.resetDecorator();
        }
        widget = widget.getLayoutParent();
      }
      while (widget && widget !== splitpane);
    },

    __attachEventHandlers: function() {
      this.addListenerOnce("appear", () => {
        this.__getSplitpaneContainer().getContentElement()
          .getDomElement()
          .addEventListener("transitionend", () => {
            if (this.getCollapsed()) {
              this.addListenerOnce("resize", e => {
                if (this.getCollapsed() && this.__getCssWidth() !== this.__savedWidth) {
                  this.__savedWidth = e.getData().width;
                  this.setCollapsed(false);
                } else {
                  this.__savedWidth = e.getData().width;
                }
              }, this);
            } else {
              this.__setDecorators();
            }
          });
      }, this);
    }
  }
});
