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

    const tabViews = this._tabsView = new qx.ui.tabview.TabView().set({
      barPosition: "left",
      contentPadding: 0
    });
    const miniWallet = this.self().createMiniWalletView().set({
      paddingRight: 10
    });
    tabViews.getChildControl("bar").add(miniWallet);

    const walletsPage = this.__walletsPage = this.__getWalletsPage();
    tabViews.add(walletsPage);

    const paymentMethodsPage = this.__paymentMethodsPage = this.__getPaymentMethodsPage();
    tabViews.add(paymentMethodsPage);

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
        maxWidth: 150
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
    _tabsView: null,
    __walletsPage: null,
    __buyCreditsPage: null,
    __paymentMethodsPage: null,
    __transactionsPage: null,
    __usagePage: null,
    __transactionsTable: null,

    __getProfilePage: function() {
      const page = new osparc.desktop.credits.ProfilePage();
      return page;
    },

    __getWalletsPage: function() {
      const title = this.tr("Credit Accounts");
      const iconSrc = "@MaterialIcons/account_balance_wallet/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      const walletsView = new osparc.desktop.wallets.WalletsView();
      walletsView.set({
        margin: 10
      });
      walletsView.addListener("buyCredits", () => this.__openBuyCredits());
      page.add(walletsView);
      return page;
    },

    __getPaymentMethodsPage: function() {
      const title = this.tr("Payment Methods");
      const iconSrc = "@FontAwesome5Solid/credit-card/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      this.__paymentMethods = new osparc.desktop.paymentMethods.PaymentMethods();
      page.add(this.__paymentMethods, {
        flex: 1
      });
      return page;
    },

    __getTransactionsPage: function() {
      const title = this.tr("Transactions");
      const iconSrc = "@FontAwesome5Solid/exchange-alt/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      const transactions = this.__transactionsTable = new osparc.desktop.credits.Transactions();
      transactions.set({
        margin: 10
      });
      page.add(transactions, { flex: 1 });
      return page;
    },

    __getUsagePage: function() {
      const title = this.tr("Usage");
      const iconSrc = "@FontAwesome5Solid/list/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      const usage = new osparc.desktop.credits.Usage();
      usage.set({
        margin: 10
      });
      page.add(usage, { flex: 1 });
      return page;
    },

    __openPage: function(page) {
      if (page) {
        this._tabsView.setSelection([page]);
        return true;
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
      if (this.__paymentMethods) {
        const paymentMethods = this.__paymentMethods.getPaymentMethods();
        const buyView = new osparc.desktop.credits.BuyCreditsStepper(
          paymentMethods.map(({idr, cardHolderName, cardNumberMasked}) => ({
            label: `${cardHolderName} ${cardNumberMasked}`,
            id: idr
          }))
        );
        const win = osparc.ui.window.Window.popUpInWindow(buyView, "Buy credits", 400, 600).set({
          resizable: false,
          movable: false
        });
        buyView.addListener("completed", () => win.close());
        win.addListener("close", () => buyView.cancelPayment())
      }
    },

    openPaymentMethods: function() {
      this.__openPage(this.__paymentMethodsPage);
    },

    openTransactions: function(fetchTransactions = false) {
      if (fetchTransactions) {
        this.__transactionsTable.refresh();
        this.__openPage(this.__transactionsPage);
      } else {
        this.__openPage(this.__transactionsPage);
      }
    },

    openUsage: function() {
      this.__openPage(this.__usagePage);
    }
  }
});
