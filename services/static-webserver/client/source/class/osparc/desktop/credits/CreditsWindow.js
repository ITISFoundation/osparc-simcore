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

    const walletsPage = this.__walletsPage = this.__getWalletsPage();
    tabViews.add(walletsPage);

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
    __walletsPage: null,
    __buyCreditsPage: null,
    __transactionsPage: null,
    __usageOverviewPage: null,
    __transactions: null,

    __getWalletsPage: function() {
      const title = this.tr("Wallets");
      const iconSrc = "@FontAwesome5Solid/folder/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      const walletsView = new osparc.desktop.wallets.WalletsView();
      walletsView.set({
        margin: 10
      });
      page.add(walletsView);
      return page;
    },

    __getBuyCreditsPage: function() {
      const title = this.tr("Buy Credits");
      const iconSrc = "@FontAwesome5Solid/dollar-sign/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      const buyCredits = new osparc.desktop.credits.BuyCredits();
      buyCredits.set({
        margin: 10
      });
      buyCredits.addListener("transactionSuccessful", e => {
        const {
          nCredits,
          totalPrice
        } = e.getData();
        this.__transactions.addRow(nCredits, totalPrice);
        this.openTransactions();
      }, this);
      page.add(buyCredits);
      return page;
    },

    __getTransactionsPage: function() {
      const title = this.tr("Transactions");
      const iconSrc = "@FontAwesome5Solid/exchange-alt/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      const transactions = this.__transactions = new osparc.desktop.credits.Transactions();
      transactions.set({
        margin: 10
      });
      page.add(transactions);
      return page;
    },

    __getUsageOverviewPage: function() {
      const title = this.tr("Usage Overview");
      const iconSrc = "@FontAwesome5Solid/list/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      const usageOverview = new osparc.component.resourceUsage.Overview();
      usageOverview.set({
        margin: 10
      });
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
