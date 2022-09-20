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

    this.getChildControl("caret");

    // Set if coming in the constructor arguments
    if (title) {
      this.setTitle(title);
    }
    if (content) {
      this.setContent(content);
    }
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
      apply: "_applyCollapsed",
      event: "changeCollapsed"
    },

    caretSize: {
      init: 20,
      nullable: false,
      check: "Integer",
      apply: "_applyCaretSize"
    }
  },

  members: {
    _innerContainer: null,
    __containerHeight: null,
    __layoutFlex: null,
    __minHeight: null,
    __contentMinHeight: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "header":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle"
          }));
          this._add(control);
          break;
        case "caret": {
          const header = this.getChildControl("header");
          control = new qx.ui.basic.Image(this.__getCaretId(this.getCollapsed())).set({
            visibility: "excluded"
          });
          header.addAt(control, 0);
          // Attach handler
          this.__attachToggler(control);
          break;
        }
        case "title": {
          const header = this.getChildControl("header");
          control = new qx.ui.basic.Label(this.getTitle());
          header.addAt(control, 1);
          // Attach handler
          this.__attachToggler(control);
          break;
        }
        case "icon": {
          const header = this.getChildControl("header");
          control = new qx.ui.basic.Image();
          header.addAt(control, 2);
          break;
        }
        case "title-btns-left": {
          const header = this.getChildControl("header");
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
            paddingLeft: 20
          });
          header.addAt(control, 3);
          break;
        }
        case "title-btns-right": {
          const header = this.getChildControl("header");
          header.addAt(new qx.ui.core.Spacer(), 4, {
            flex: 1
          });
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(0)).set({
            paddingRight: 8
          });
          header.addAt(control, 5);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    toggleCollapsed: function() {
      this.setCollapsed(!this.getCollapsed());
    },

    getTitleBar: function() {
      return this.getChildControl("header");
    },

    getTitleLabel: function() {
      return this.getChildControl("title");
    },

    getTitleBarBtnsContainerLeft: function() {
      return this.getChildControl("title-btns-left");
    },

    getTitleBarBtnsContainerRight: function() {
      return this.getChildControl("title-btns-right");
    },

    _applyCollapsed: function(collapsed) {
      if (this.getContent()) {
        this.getChildControl("caret").setSource(this.__getCaretId(collapsed));
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
        // this._innerContainer.setHeight(collapsed ? 0 : this.__containerHeight);
        this._innerContainer.setVisibility(collapsed ? "excluded" : "visible");
      }
    },

    _applyContent: function(content, oldContent) {
      if (this._innerContainer === null) {
        this._innerContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow()).set({
          padding: 0
        });
        this._addAt(this._innerContainer, 1, {
          flex: 1
        });

        this._innerContainer.addListener("changeHeight", e => {
          const height = e.getOldData();
          if (height != 0) {
            this.__containerHeight = height;
          }
        }, this);

        content.addListenerOnce("appear", () => {
          content.getContentElement().getDomElement().style.transform = "translateZ(0)";
        });
      }

      this._innerContainer.removeAll();
      this._innerContainer.add(content);
      this._innerContainer.setHeight(this.getCollapsed() ? 0 : this.__containerHeight);

      const caret = this.getChildControl("caret");
      if (content) {
        caret.show();
      } else {
        caret.exclude();
      }
    },

    _applyCaretSize: function(size) {
      this.getChildControl("caret").setSource(this.__getCaretId(this.getCollapsed()));
    },

    _applyTitle: function(title) {
      this.getChildControl("title").setValue(title);
    },

    _applyIcon: function(icon) {
      this.getChildControl("icon").setSource(icon);
    },

    __getCaretId: function(collapsed) {
      const caretSize = this.getCaretSize();
      const moreCaret = this.self().COLLAPSED_CARET;
      const lessCaret = this.self().EXPANDED_CARET;
      return collapsed ? moreCaret + caretSize : lessCaret + caretSize;
    },

    __attachToggler: function(control) {
      control.addListener("tap", () => {
        this.toggleCollapsed();
      }, this);
    }
  }
});
