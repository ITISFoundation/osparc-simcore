/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)
     * Odei Maiz (odeimaiz)

************************************************************************ */
/* eslint-disable no-use-before-define */

/**
 * Display widget with a title bar and collapsible content.
 */
qx.Class.define("osparc.component.widget.CollapsibleView", {
  extend: qx.ui.core.Widget,

  construct: function(title, content) {
    this.base(arguments);

    // Layout
    this._setLayout(new qx.ui.layout.VBox());

    // Title bar
    this.__titleBar = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    })).set({
      allowGrowX: false
    });
    this._add(this.__titleBar);

    this.__caret = this.getChildControl("caret");

    // Set if coming in the constructor arguments
    if (title) {
      this.setTitle(title);
    }
    if (content) {
      this.setContent(content);
    }

    // Attach handlers
    this.__attachEventHandlers();
  },

  statics: {
    COLLAPSED_CARET: "@MaterialIcons/chevron_right/",
    EXPANDED_CARET: "@MaterialIcons/expand_more/"
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

    caretSize: {
      init: 20,
      nullable: false,
      check: "Integer",
      apply: "_applyCaretSize"
    }
  },

  members: {
    __titleBar: null,
    __titleLabel: null,
    __caret: null,
    __innerContainer: null,
    __containerHeight: null,
    __layoutFlex: null,
    __minHeight: null,
    __contentMinHeight: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "caret":
          control = new qx.ui.basic.Image(this.__getCaretId(this.getCollapsed())).set({
            visibility: "excluded"
          });
          this.__titleBar.addAt(control, 0);
          break;
        case "title":
          control = new qx.ui.basic.Atom(this.getTitle());
          this.__titleBar.addAt(control, 1);
          break;
      }
      return control || this.base(arguments, id);
    },

    toggleCollapsed: function() {
      this.setCollapsed(!this.getCollapsed());
    },

    getTitleBar: function() {
      return this.__titleBar;
    },

    _applyCollapsed: function(collapsed) {
      if (this.getContent()) {
        this.__caret.setSource(this.__getCaretId(collapsed));
        if (collapsed) {
          this.__minHeight = this.getMinHeight();
          if (this.getContent()) {
            this.__contentMinHeight = this.getContent().getMinHeight();
            this.getContent().setMinHeight(0);
          }
          this.setMinHeight(0);
          if (this.getLayoutProperties().flex) {
            this.__layoutFlex = this.getLayoutProperties().flex;
            this.setLayoutProperties({
              flex: 0
            });
          }
        } else {
          this.setMinHeight(this.__minHeight);
          if (this.getContent()) {
            this.getContent().setMinHeight(this.__contentMinHeight);
          }
          if (this.__layoutFlex) {
            this.setLayoutProperties({
              flex: this.__layoutFlex
            });
          }
        }
        // this.__innerContainer.setHeight(collapsed ? 0 : this.__containerHeight);
        this.__innerContainer.setVisibility(collapsed ? "excluded" : "visible");
      }
    },

    _applyContent: function(content, oldContent) {
      if (this.__innerContainer === null) {
        this.__innerContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow()).set({
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
      this.__innerContainer.add(content);
      this.__innerContainer.setHeight(this.getCollapsed() ? 0 : this.__containerHeight);

      if (content) {
        this.__caret.show();
      } else {
        this.__caret.exclude();
      }
    },

    _applyTitle: function(title) {
      this.__titleLabel = this.getChildControl("title");
      this.__titleLabel.setLabel(title);
    },

    _applyCaretSize: function(size) {
      this.__caret.setSource(this.__getCaretId(this.getCollapsed()));
    },

    __getCaretId: function(collapsed) {
      const caretSize = this.getCaretSize();
      const moreCaret = this.self().COLLAPSED_CARET;
      const lessCaret = this.self().EXPANDED_CARET;
      return collapsed ? moreCaret + caretSize : lessCaret + caretSize;
    },

    __attachEventHandlers: function() {
      this.__titleBar.addListener("tap", () => {
        this.toggleCollapsed();
      }, this);
    }
  }
});
