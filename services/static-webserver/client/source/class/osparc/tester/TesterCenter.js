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

qx.Class.define("osparc.tester.TesterCenter", {
  extend: osparc.ui.window.TabbedView,

  construct: function() {
    this.base(arguments);

    const miniProfile = osparc.desktop.account.MyAccount.createMiniProfileView().set({
      paddingRight: 10
    });
    this.addWidgetOnTopOfTheTabs(miniProfile);

    this.__addStaticsPage();
  },

  members: {
    __addStaticsPage: function() {
      const title = this.tr("Maintenance");
      const iconSrc = "@FontAwesome5Solid/wrench/22";
      const maintenance = new osparc.tester.Statics();
      this.addTab(title, iconSrc, maintenance);
    },
  }
});
