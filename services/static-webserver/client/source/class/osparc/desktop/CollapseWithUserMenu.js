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
            width: 2,
            padding: 0,
            margin: [7, 0],
            backgroundColor: "default-button-disabled-background"
          });
          this._add(control);
          break;
        case "back-to-dashboard-button":
          control = new osparc.ui.form.FetchButton(this.tr("Dashboard"), "@FontAwesome5Solid/arrow-left/14").set({
            appearance: "fab-button",
            alignY: "middle",
            padding: [5, 16],
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS
          });
          osparc.utils.Utils.setIdToWidget(control, "dashboardBtn");
          control.addListener("execute", () => this.fireEvent("backToDashboardPressed"));
          this._add(control);
          break;
        case "user-menu-button":
          control = new osparc.navigation.UserMenuButton();
          osparc.WatchDog.getInstance().bind("online", control, "backgroundColor", {
            converter: on => on ? "background-main-4" : "red"
          });
          control.getChildControl("label").exclude();
          control.populateMenuCompact();
          this._add(control);
          break;
        case "collapse-expand-stack": {
          control = new qx.ui.container.Stack();

          const collapseNavBarBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/chevron-up/14").set({
            appearance: "fab-button",
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS
          });
          control.add(collapseNavBarBtn);
          collapseNavBarBtn.addListener("execute", () => {
            this.setCollapsed(true);
            this.fireEvent("collapseNavBar");
          });

          const expandNavBarBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/chevron-down/14").set({
            appearance: "fab-button",
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS
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
      backToDashboardBtn.set({
        marginRight: 10
      });
      backToDashboardBtn.exclude();

      const userMenuButton = this.getChildControl("user-menu-button");
      userMenuButton.set({
        marginRight: 1,
        marginTop: 3
      });
      userMenuButton.exclude();

      const collapseExpandStack = this.getChildControl("collapse-expand-stack");
      collapseExpandStack.set({
        padding: 8,
        marginRight: 4
      });
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
