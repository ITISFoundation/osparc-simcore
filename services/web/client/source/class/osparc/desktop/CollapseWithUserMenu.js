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

qx.Class.define("osparc.desktop.CollapseWithUserMenu", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this.__buildLayout();
  },

  events: {
    "backToDashboardPressed": "qx.event.type.Event",
    "collapseNavBar": "qx.event.type.Event",
    "expandNavBar": "qx.event.type.Event"
  },

  properties: {
    collapsed: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeCollapsed",
      apply: "__applyCollapsed"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "separator":
          control = new qx.ui.toolbar.Separator().set({
            padding: 0,
            margin: 0,
            backgroundColor: "contrasted-background++"
          });
          this._add(control);
          break;
        case "back-to-dashboard-button":
          control = new osparc.ui.form.FetchButton(this.tr("Dashboard"), "@FontAwesome5Solid/arrow-left/16").set({
            font: "text-14",
            backgroundColor: "contrasted-background+"
          });
          osparc.utils.Utils.setIdToWidget(control, "dashboardBtn");
          control.addListener("execute", () => this.fireEvent("backToDashboardPressed"));
          this._add(control);
          break;
        case "user-menu-button":
          control = new osparc.navigation.UserMenuButton().set({
            backgroundColor: "contrasted-background+"
          });
          osparc.io.WatchDog.getInstance().bind("online", control, "backgroundColor", {
            converter: on => on ? "contrasted-background+" : "red"
          });
          control.getChildControl("label").exclude();
          control.getMenu().set({
            backgroundColor: "contrasted-background+"
          });
          control.populateExtendedMenu();
          this._add(control);
          break;
        case "collapse-expand-stack": {
          control = new qx.ui.container.Stack();

          const collapseNavBarBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/chevron-up/14").set({
            backgroundColor: "contrasted-background+"
          });
          control.add(collapseNavBarBtn);
          collapseNavBarBtn.addListener("execute", () => {
            this.setCollapsed(true);
            this.fireEvent("collapseNavBar");
          });

          const expandNavBarBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/chevron-down/14").set({
            backgroundColor: "contrasted-background+"
          });
          control.add(expandNavBarBtn);
          expandNavBarBtn.addListener("execute", () => {
            this.setCollapsed(false);
            this.fireEvent("expandNavBar");
          });

          this._add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const separator = this.getChildControl("separator");
      separator.exclude();

      const backToDashboardBtn = this.getChildControl("back-to-dashboard-button");
      backToDashboardBtn.exclude();

      const userMenuButton = this.getChildControl("user-menu-button");
      userMenuButton.exclude();

      this.getChildControl("collapse-expand-stack");
    },

    __applyCollapsed: function(collapsed) {
      this.getChildControl("separator").setVisibility(collapsed ? "visible" : "excluded");
      this.getChildControl("back-to-dashboard-button").setVisibility(collapsed ? "visible" : "excluded");
      this.getChildControl("user-menu-button").setVisibility(collapsed ? "visible" : "excluded");
      const collapseExpandStack = this.getChildControl("collapse-expand-stack");
      collapseExpandStack.setSelection([collapseExpandStack.getSelectables()[collapsed ? 1 : 0]]);
    }
  }
});
