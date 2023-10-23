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

qx.Class.define("osparc.desktop.credits.BillingCenter", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      padding: 20,
      paddingLeft: 10
    });

    const tabViews = this.__tabsView = new qx.ui.tabview.TabView().set({
      barPosition: "left",
      contentPadding: 0
    });
    tabViews.getChildControl("bar").add(this.self().createMiniWalletView());

    const overviewPage = this.__overviewPage = this.__getOverviewPage();
    tabViews.add(overviewPage);

    const walletsPage = this.__walletsPage = this.__getWalletsPage();
    tabViews.add(walletsPage);

    const paymentMethodsPage = this.__paymentMethodsPage = this.__getPaymentMethodsPage();
    tabViews.add(paymentMethodsPage);

    const buyCreditsPage = this.__buyCreditsPage = this.__getBuyCreditsPage();
    tabViews.add(buyCreditsPage);

    const activityPage = this.__activityPage = this.__getActivityPage();
    tabViews.add(activityPage);

    const transactionsPage = this.__transactionsPage = this.__getTransactionsPage();
    tabViews.add(transactionsPage);

    if (osparc.data.Permissions.getInstance().canDo("usage.all.read")) {
      const usagePage = this.__usagePage = this.__getUsagePage();
      tabViews.add(usagePage);
    }

    this._add(tabViews);
  },

  statics: {
    createMiniWalletView: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(8)).set({
        alignX: "center",
        minWidth: 120,
        maxWidth: 150,
        paddingRight: 10
      });

      const store = osparc.store.Store.getInstance();
      const creditsIndicator = new osparc.desktop.credits.CreditsIndicator();
      store.bind("contextWallet", creditsIndicator, "wallet");
      layout.add(creditsIndicator);

      layout.add(new qx.ui.core.Spacer(15, 15));

      return layout;
    }
  },

  members: {
    __tabsView: null,
    __overviewPage: null,
    __walletsPage: null,
    __buyCreditsPage: null,
    __paymentMethodsPage: null,
    __activityPage: null,
    __transactionsPage: null,
    __usagePage: null,
    __buyCredits: null,
    __transactionsTable: null,

    __getOverviewPage: function() {
      const title = this.tr("Summary");
      const iconSrc = "@FontAwesome5Solid/table/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const overview = new osparc.desktop.credits.Summary();
      overview.set({
        margin: 10
      });
      overview.addListener("buyCredits", e => {
        this.__openBuyCredits();
        const {
          walletId
        } = e.getData();
        const store = osparc.store.Store.getInstance();
        const found = store.getWallets().find(wallet => wallet.getWalletId() === parseInt(walletId));
        if (found) {
          this.__buyCredits.setWallet(found);
        }
      });
      overview.addListener("toWallets", () => this.openWallets());
      overview.addListener("toActivity", () => this.__openActivity());
      overview.addListener("toTransactions", () => this.__openTransactions());
      page.add(overview);
      return page;
    },

    __getProfilePage: function() {
      const page = new osparc.desktop.credits.ProfilePage();
      page.showLabelOnTab();
      return page;
    },

    __getWalletsPage: function() {
      const title = this.tr("Credit Accounts");
      const iconSrc = "@MaterialIcons/account_balance_wallet/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const walletsView = new osparc.desktop.wallets.WalletsView();
      walletsView.set({
        margin: 10
      });
      walletsView.addListener("buyCredits", e => {
        this.__openBuyCredits();
        const {
          walletId
        } = e.getData();
        const store = osparc.store.Store.getInstance();
        const found = store.getWallets().find(wallet => wallet.getWalletId() === parseInt(walletId));
        if (found) {
          this.__buyCredits.setWallet(found);
        }
      });
      page.add(walletsView);
      return page;
    },

    __getPaymentMethodsPage: function() {
      const title = this.tr("Payment Methods");
      const iconSrc = "@FontAwesome5Solid/credit-card/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const paymentMethods = new osparc.desktop.paymentMethods.PaymentMethods();
      paymentMethods.set({
        margin: 10
      });
      page.add(paymentMethods);
      return page;
    },

    __getBuyCreditsPage: function() {
      const title = this.tr("Buy Credits");
      const iconSrc = "@FontAwesome5Solid/dollar-sign/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const buyCredits = this.__buyCredits = new osparc.desktop.credits.BuyCredits();
      buyCredits.set({
        margin: 10
      });
      buyCredits.addListener("transactionCompleted", () => this.__openTransactions(true), this);
      page.add(buyCredits);
      return page;
    },

    __getActivityPage: function() {
      const title = this.tr("Activity");
      const iconSrc = "@FontAwesome5Solid/list/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const activity = new osparc.desktop.credits.Activity();
      activity.set({
        margin: 10
      });
      page.add(activity);
      return page;
    },

    __getTransactionsPage: function() {
      const title = this.tr("Transactions");
      const iconSrc = "@FontAwesome5Solid/exchange-alt/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const transactions = this.__transactionsTable = new osparc.desktop.credits.Transactions();
      transactions.set({
        margin: 10
      });
      page.add(transactions);
      return page;
    },

    __getUsagePage: function() {
      const title = this.tr("Usage");
      const iconSrc = "@FontAwesome5Solid/list/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const usage = new osparc.desktop.credits.Usage();
      usage.set({
        margin: 10
      });
      page.add(usage);
      return page;
    },

    __openPage: function(page) {
      if (page) {
        this.__tabsView.setSelection([page]);
        return true;
      }
      return false;
    },

    openOverview: function() {
      if (this.__overviewPage) {
        return this.__openPage(this.__overviewPage);
      }
      return false;
    },

    openWallets: function() {
      if (this.__walletsPage) {
        return this.__openPage(this.__walletsPage);
      }
      return false;
    },

    __openBuyCredits: function() {
      this.__openPage(this.__buyCreditsPage);
    },

    __openActivity: function() {
      this.__openPage(this.__activityPage);
    },

    __openTransactions: function(fetchTransactions = false) {
      if (fetchTransactions) {
        this.__transactionsTable.refetchData();
        this.__openPage(this.__transactionsPage);
      } else {
        this.__openPage(this.__transactionsPage);
      }
    }
  }
});
