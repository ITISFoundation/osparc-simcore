/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.admin.AdminCenter", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      padding: 10
    });

    const tabViews = new qx.ui.tabview.TabView().set({
      barPosition: "left",
      contentPadding: 0
    });
    const miniProfile = osparc.desktop.credits.MyAccount.createMiniProfileView().set({
      paddingRight: 10
    });
    tabViews.getChildControl("bar").add(miniProfile);

    const pricingPlans = this.__getPricingPlansPage();
    tabViews.add(pricingPlans);

    const maintenance = this.__getMaintenancePage();
    tabViews.add(maintenance);

    this._add(tabViews, {
      flex: 1
    });
  },

  members: {
    __widgetToPage: function(title, iconSrc, widget) {
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      widget.set({
        margin: 10
      });
      page.add(widget, {
        flex: 1
      });
      return page;
    },

    __getPricingPlansPage: function() {
      const title = this.tr("Pricing Plans");
      const iconSrc = "@FontAwesome5Solid/dollar-sign/22";
      const pricingPlans = new osparc.pricing.PlanManager();
      const page = this.__widgetToPage(title, iconSrc, pricingPlans);
      return page;
    },

    __getMaintenancePage: function() {
      const title = this.tr("Maintenance");
      const iconSrc = "@FontAwesome5Solid/wrench/22";
      const maintenance = new osparc.admin.Maintenance();
      const page = this.__widgetToPage(title, iconSrc, maintenance);
      return page;
    }
  }
});
