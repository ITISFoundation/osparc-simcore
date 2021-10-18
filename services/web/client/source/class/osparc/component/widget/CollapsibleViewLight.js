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
        case "caret-collapsed":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/angle-right/14").set({
            toolTipText: this.tr("Expand"),
            backgroundColor: "transparent",
            padding: 4,
            allowGrowX: false,
            allowGrowY: true,
            alignY: "middle"
          });
          control.addListener("execute", () => this.setCollapsed(false));
          this._addAt(control, 1);
          break;
        case "caret-expanded":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/angle-left/14").set({
            toolTipText: this.tr("Collapse"),
            backgroundColor: "transparent",
            padding: 4,
            allowGrowX: false,
            allowGrowY: true,
            alignY: "middle"
          });
          control.addListener("execute", () => this.setCollapsed(true));
          this._addAt(control, 2);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyCollapsed: function(collapsed) {
      if (this.getContent()) {
        this.getContent().setVisibility(collapsed ? "excluded" : "visible");
      }
      this.getChildControl("caret-collapsed").setVisibility(collapsed ? "visible" : "excluded");
      this.getChildControl("caret-expanded").setVisibility(collapsed ? "excluded" : "visible");
    },

    __applyContent: function(content) {
      this._removeAll();

      this._addAt(content, 0, {
        flex: 1
      });
      this.setCollapsed(false);
    }
  }
});
