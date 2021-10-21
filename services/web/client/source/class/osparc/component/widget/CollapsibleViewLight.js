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

qx.Class.define("osparc.component.widget.CollapsibleViewLight", {
  extend: qx.ui.core.Widget,

  construct: function(content) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    if (content) {
      this.setContent(content);
    }

    this.initCollapsed();
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

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "expand-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/angle-right/14").set({
            toolTipText: this.tr("Expand"),
            backgroundColor: "transparent",
            padding: 4,
            allowGrowX: false,
            allowGrowY: true,
            alignY: "middle"
          });
          control.addListener("execute", () => this.setCollapsed(false));
          break;
        case "collapse-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/angle-left/14").set({
            toolTipText: this.tr("Collapse"),
            backgroundColor: "transparent",
            padding: 4,
            allowGrowX: false,
            allowGrowY: true,
            alignY: "middle"
          });
          control.addListener("execute", () => this.setCollapsed(true));
          break;
        case "caret-collapsed-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
            width: 15
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
            width: 15
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
      if (this.getContent()) {
        this.getContent().setVisibility(collapsed ? "excluded" : "visible");
      }
    },

    __applyContent: function(content, oldContent) {
      if (oldContent) {
        this._remove(oldContent);
      }

      this._addAt(content, 0, {
        flex: 1
      });
      this.setCollapsed(false);
    }
  }
});
