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

    this.__addSocketMessagesPage();
    this.__addConsoleErrorsPage();
    this.__addStaticsPage();
  },

  members: {
    __addSocketMessagesPage: function() {
      const title = this.tr("Socket Messages");
      const iconSrc = "@FontAwesome5Solid/exchange-alt/22";
      const webSocketMessages = new osparc.tester.WebSocketMessages();
      this.addTab(title, iconSrc, webSocketMessages);
    },

    __addConsoleErrorsPage: function() {
      const title = this.tr("Console Errors");
      const iconSrc = "@FontAwesome5Solid/times/22";
      const consoleErrors = new osparc.tester.ConsoleErrors();
      this.addTab(title, iconSrc, consoleErrors);
    },

    __addStaticsPage: function() {
      const title = this.tr("Statics");
      const iconSrc = "@FontAwesome5Solid/wrench/22";
      const maintenance = new osparc.tester.Statics();
      this.addTab(title, iconSrc, maintenance);
    },
  }
});
