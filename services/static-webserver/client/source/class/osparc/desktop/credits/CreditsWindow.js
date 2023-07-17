/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.CreditsWindow", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "credits", this.tr("Credits"));

    const viewWidth = 900;
    const viewHeight = 600;

    this.set({
      layout: new qx.ui.layout.Grow(),
      modal: true,
      width: viewWidth,
      height: viewHeight,
      showMaximize: false,
      showMinimize: false,
      resizable: false,
      appearance: "service-window"
    });

    const tabViews = this.__tabsView = new qx.ui.tabview.TabView().set({
      barPosition: "left",
      contentPadding: 0
    });

    const buyCreditsPage = this.__buyCreditsPage = this.__getBuyCreditsPage();
    tabViews.add(buyCreditsPage);

    const transactionsPage = this.__transactionsPage = this.__getTransactionsPage();
    tabViews.add(transactionsPage);

    const usageOverviewPage = this.__usageOverviewPage = this.__getUsageOverviewPage();
    tabViews.add(usageOverviewPage);

    this.add(tabViews);
  },

  statics: {
    openWindow: function() {
      const preferencesWindow = new osparc.desktop.credits.CreditsWindow();
      preferencesWindow.center();
      preferencesWindow.open();
      return preferencesWindow;
    }
  },

  members: {
    __tabsView: null,
    __buyCreditsPage: null,
    __transactionsPage: null,
    __usageOverviewPage: null,

    __getBuyCreditsPage: function() {
      const title = this.tr("Buy Credits");
      const iconSrc = "@FontAwesome5Solid/dollar-sign/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      const usageOverview = new osparc.desktop.credits.BuyCredits();
      page.add(usageOverview);
      return page;
    },

    __getTransactionsPage: function() {
      const title = this.tr("Transactions");
      const iconSrc = "@FontAwesome5Solid/exchange-alt/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      const usageOverview = new osparc.desktop.credits.BuyCredits();
      page.add(usageOverview);
      return page;
    },

    __getUsageOverviewPage: function() {
      const title = this.tr("Usage Overview");
      const iconSrc = "@FontAwesome5Solid/list/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      const usageOverview = new osparc.component.resourceUsage.Overview();
      page.add(usageOverview);
      return page;
    },

    __openPage: function(page) {
      if (page) {
        this.__tabsView.setSelection([page]);
      }
    },

    openBuyCredits: function() {
      this.__openPage(this.__buyCreditsPage);
    },

    openTransactions: function() {
      this.__openPage(this.__transactionsPage);
    },

    openUsageOverview: function() {
      this.__openPage(this.__usageOverviewPage);
    }
  }
});
