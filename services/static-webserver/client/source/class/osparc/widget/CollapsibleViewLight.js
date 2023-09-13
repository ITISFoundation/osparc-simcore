/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.widget.CollapsibleViewLight", {
  extend: qx.ui.core.Widget,

  construct: function(content) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    if (content) {
      this.setContent(content);
    }

    this.initCollapsed();

    this.addListener("changeCollapsed", e => {
      const collapsed = e.getData();
      if (collapsed) {
        this.precollapseWidth = this.getBounds().width;
      }
    }, this);
  },

  properties: {
    content: {
      check: "qx.ui.core.Widget",
      nullable: true,
      apply: "__applyContent"
    },

    collapsed: {
      init: false,
      check: "Boolean",
      apply: "__applyCollapsed",
      event: "changeCollapsed"
    }
  },

  statics: {
    CARET_WIDTH: 15,

    styleCollapseExpandButton: function(btn) {
      btn.set({
        backgroundColor: "transparent",
        padding: 4,
        allowGrowX: false,
        allowGrowY: true,
        alignY: "middle"
      });
      btn.getContentElement().setStyles({
        "border-radius": "0px"
      });
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "scroll-content":
          control = new qx.ui.container.Scroll();
          this._addAt(control, 0, {
            flex: 1
          });
          break;
        case "expand-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/angle-right/14").set({
            toolTipText: this.tr("Expand")
          });
          this.self().styleCollapseExpandButton(control);
          control.addListener("execute", () => this.setCollapsed(false));
          break;
        case "collapse-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/angle-left/14").set({
            toolTipText: this.tr("Collapse")
          });
          this.self().styleCollapseExpandButton(control);
          control.addListener("execute", () => this.setCollapsed(true));
          break;
        case "caret-collapsed-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
            width: this.self().CARET_WIDTH
          });
          const expandBtn = this.getChildControl("expand-button");
          control.add(expandBtn, {
            flex: 1
          });
          this.bind("collapsed", control, "visibility", {
            converter: collapsed => collapsed ? "visible" : "excluded"
          });
          this._addAt(control, 1);
          break;
        }
        case "caret-expanded-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
            width: this.self().CARET_WIDTH
          });
          const collapseBtn = this.getChildControl("collapse-button");
          control.add(collapseBtn, {
            flex: 1
          });
          this.bind("collapsed", control, "visibility", {
            converter: collapsed => collapsed ? "excluded" : "visible"
          });
          this._addAt(control, 2);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyCollapsed: function(collapsed) {
      const scrollContent = this.getChildControl("scroll-content");
      if (scrollContent) {
        scrollContent.setVisibility(collapsed ? "excluded" : "visible");
      }
    },

    __applyContent: function(content, oldContent) {
      const scrollContent = this.getChildControl("scroll-content");
      if (oldContent) {
        scrollContent.remove(oldContent);
      }
      scrollContent.add(content);

      this.setCollapsed(false);
    }
  }
});
