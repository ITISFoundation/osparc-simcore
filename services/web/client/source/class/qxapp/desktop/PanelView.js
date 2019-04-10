/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */
/* eslint-disable no-use-before-define */

/**
 * Display widget with a title bar and collapsible content.
 */
qx.Class.define("qxapp.desktop.PanelView", {

  extend: qx.ui.core.Widget,

  construct: function(title, content) {
    this.base(arguments);

    // Layout
    this._setLayout(new qx.ui.layout.VBox());

    // Title bar
    this.__titleBar = new qx.ui.container.Composite(new qx.ui.layout.HBox(5))
      .set({
        appearance: "panelview-titlebar"
      });
    this._add(this.__titleBar);

    // Set if coming in the constructor arguments
    if (title) {
      this.setTitle(title);
    }
    if (content) {
      this.setContent(content);
    }

    // Transition effect
    this.setDecorator("panelview");

    // Attach handlers
    this.__attachEventHandlers();
  },

  statics: {
    MORE_CARET: "@MaterialIcons/expand_more/20",
    LESS_CARET: "@MaterialIcons/expand_less/20"
  },

  properties: {
    title: {
      check: "String",
      nullable: true,
      apply: "_applyTitle"
    },

    content: {
      check: "qx.ui.core.Widget",
      nullable: true,
      apply: "_applyContent"
    },

    collapsed: {
      init: false,
      check: "Boolean",
      apply: "_applyCollapsed"
    },

    sideCollapsed: {
      init: false,
      check: "Boolean",
      apply: "_applySideCollapsed"
    }
  },

  members: {
    __titleBar: null,
    __titleLabel: null,
    __caret: null,
    __innerContainer: null,
    __containerHeight: null,
    __layoutFlex: null,

    toggleCollapsed: function() {
      this.setCollapsed(!this.getCollapsed());
    },

    toggleSideCollapsed: function() {
      this.setSideCollapsed(!this.getSideCollapsed());
    },

    _applyCollapsed: function(collapsed) {
      if (this.getContent()) {
        this.__caret.setSource(collapsed ? this.self().MORE_CARET : this.self().LESS_CARET);
        if (collapsed) {
          if (this.getLayoutProperties().flex) {
            this.__layoutFlex = this.getLayoutProperties().flex;
            this.setLayoutProperties({
              flex: 0
            });
          }
          if (this.__innerContainer.getContentElement().getDomElement() == null) { // eslint-disable-line no-eq-null
            this.__innerContainer.exclude();
          }
        } else if (this.__layoutFlex) {
          this.setLayoutProperties({
            flex: this.__layoutFlex
          });
        }
        this.__innerContainer.setHeight(collapsed ? 0 : this.__containerHeight);
      }
    },

    _applyContent: function(content, oldContent) {
      if (this.__innerContainer === null) {
        this.__innerContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow()).set({
          appearance: "panelview-content",
          visibility: this.getCollapsed() ? "excluded" : "visible",
          padding: 0
        });
        this._addAt(this.__innerContainer, 1, {
          flex: 1
        });

        this.__innerContainer.addListener("changeHeight", e => {
          const height = e.getOldData();
          if (height != 0) {
            this.__containerHeight = height;
          }
        }, this);

        content.addListenerOnce("appear", () => {
          content.getContentElement().getDomElement().style.transform = "translateZ(0)";
        });
      }

      this.__innerContainer.removeAll();
      content.setMinHeight(0);
      this.__innerContainer.add(content);

      if (this.__caret === null) {
        this.__caret = new qx.ui.basic.Image(this.getCollapsed() ? this.self().MORE_CARET : this.self().LESS_CARET).set({
          marginTop: 2
        });
        this.__titleBar.add(this.__caret);
      }
    },

    _applyTitle: function(title) {
      if (this.__titleLabel) {
        this.__titleLabel.setValue(title);
      } else {
        this.__titleLabel = new qx.ui.basic.Label(title)
          .set({
            appearance: "panelview-titlebar-label",
            font: "title-14"
          });
        this.__titleBar.add(this.__titleLabel);
      }
    },

    __attachEventHandlers: function() {
      this.__titleBar.addListener("tap", () => {
        this.toggleCollapsed();
      }, this);
    },

    _applySideCollapsed: function(sideCollapse, old) {
      this.setCollapsed(sideCollapse);
    }
  }

});
