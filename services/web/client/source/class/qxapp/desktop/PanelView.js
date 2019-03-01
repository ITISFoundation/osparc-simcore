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

/**
 * Display widget with a title bar and collapsible content.
 */
qx.Class.define("qxapp.desktop.PanelView", {
  extend: qx.ui.core.Widget,

  construct: function(title, content) {
    this.base(arguments);

    // Internal props
    this.__titleBar = null;
    this.__titleLabel = null;

    // Layout
    const layout = new qx.ui.layout.VBox();
    this._setLayout(layout);

    // Title bar
    this.__titleBar = new qx.ui.container.Composite(new qx.ui.layout.HBox(5))
      .set({
        appearance: "titlebar"
      });
    this._add(this.__titleBar);

    if (title){
      this.__titleLabel = new qx.ui.basic.Label(title)
        .set({
          appearance: "titlebar-label"
        });
      this.__titleBar.add(this.__titleLabel);
    }

    // Content
    if (content) {
      content.setAppearance("titlebar-content");
      this.setContent(content);
    }

    // Atach handlers
    this.__attachEventHandlers();
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

    contentVisibility: {
      init: true,
      check: "Boolean",
      apply: "_applyContentVisibility"
    }
  },

  members: {

    toggleContentVisibility: function() {
      this.setContentVisibility(!this.getContentVisibility());
    },

    _applyContentVisibility: function(isVisible) {
      if (this.getContent()) {
        this.getContent().setVisibility(isVisible ? "visible" : "excluded");
      }
    },

    _applyContent: function(content, oldContent) {
      const contentIndex = this._indexOf(oldContent);
      if (contentIndex > -1) {
        this._removeAt(contentIndex);
      }
      content.setAppearance("titlebar-content");
      this._addAt(content, 1);
    },

    _applyTitle: function(title) {
      if (this.__titlelabel) {
        this.__titleLabel.setValue(title);
      } else {
        this.__titleLabel = new qx.ui.basic.Label(title)
          .set({
            appearance: "titlebar-label"
          });
        this.__titleBar.add(this.__titleLabel);
      }
    },

    __attachEventHandlers() {
      this.__titleBar.addListener("tap", () => {
        this.toggleContentVisibility();
      }, this);
    }
  }

});
