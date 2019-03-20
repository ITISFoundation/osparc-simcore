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
    this.setDecorator("panelview-collapse-transition");

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

    contentVisibility: {
      init: true,
      check: "Boolean",
      apply: "_applyContentVisibility"
    }
  },

  members: {
    __titleBar: null,
    __titleLabel: null,
    __caret: null,
    __innerContainer: null,
    __containerHeight: null,
    __layoutFlex: null,

    toggleContentVisibility: function() {
      this.setContentVisibility(!this.getContentVisibility());
    },

    _applyContentVisibility: function(isVisible) {
      if (this.getContent()) {
        this.__caret.setSource(isVisible ? this.self().LESS_CARET : this.self().MORE_CARET);
        if (isVisible) {
          this.__innerContainer.show();
          this.setLayoutProperties({
            flex: this.__layoutFlex || 0
          });
        } else {
          this.__layoutFlex = this.getLayoutProperties().flex;
          this.setLayoutProperties({
            flex: 0
          });
          if (this.__innerContainer.getContentElement().getDomElement() == null) { // eslint-disable-line no-eq-null
            this.__innerContainer.exclude();
          }
        }
        this.__innerContainer.setDecorator(isVisible ? "panelview-open-collapse-transition" : "panelview-collapse-transition");
        this.__innerContainer.setHeight(isVisible ? this.__containerHeight : 0);
      }
    },

    _applyContent: function(content, oldContent) {
      if (this.__innerContainer === null) {
        this.__innerContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow()).set({
          appearance: "panelview-content",
          decorator: "panelview-content",
          visibility: this.getContentVisibility() ? "visible" : "excluded"
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

        this.__innerContainer.addListenerOnce("appear", () => {
          this.__innerContainer.getContentElement().getDomElement()
            .addEventListener("transitionend", () => {
              this.__innerContainer.setDecorator("panelview-content");
              if (this.__innerContainer.getHeight() === 0) {
                this.__innerContainer.exclude();
              }
            });
        }, this);
      }

      this.__innerContainer.removeAll();
      content.setMinHeight(0);
      this.__innerContainer.add(content);

      if (this.__caret === null) {
        this.__caret = new qx.ui.basic.Image(this.getContentVisibility() ? this.self().LESS_CARET : this.self().MORE_CARET).set({
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
        this.toggleContentVisibility();
      }, this);
    }
  }

});
