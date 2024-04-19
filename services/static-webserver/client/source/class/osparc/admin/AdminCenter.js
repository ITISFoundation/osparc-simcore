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
  extend: osparc.ui.window.TabbedView,

  construct: function() {
    this.base(arguments);

    const miniProfile = osparc.desktop.account.MyAccount.createMiniProfileView().set({
      paddingRight: 10
    });
    this.addWidgetOnTopOfTheTabs(miniProfile);

    this.__addPricingPlansPage();
    this.__addMaintenancePage();
  },

  members: {
    __addPricingPlansPage: function() {
      const title = this.tr("Pricing Plans");
      const iconSrc = "@FontAwesome5Solid/dollar-sign/22";
      const pricingPlans = new osparc.pricing.PlanManager();
      this.addTab(title, iconSrc, pricingPlans);
    },

    __addMaintenancePage: function() {
      const title = this.tr("Maintenance");
      const iconSrc = "@FontAwesome5Solid/wrench/22";
      const maintenance = new osparc.admin.Maintenance();
      this.addTab(title, iconSrc, maintenance);
    }
  }
});
