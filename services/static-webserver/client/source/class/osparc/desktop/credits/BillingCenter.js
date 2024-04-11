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
  extend: osparc.ui.window.TabbedView,

  construct: function() {
    this.base(arguments);

    const miniWallet = this.self().createMiniWalletView().set({
      paddingRight: 10
    });
    this.addWidgetOnTopOfTheTabs(miniWallet);

    this.__walletsPage = this.__addWalletsPage();
    this.__paymentMethodsPage = this.__addPaymentMethodsPage();
    this.__transactionsPage = this.__addTransactionsPage();

    if (osparc.data.Permissions.getInstance().canDo("usage.all.read")) {
      this.__usagePage = this.__addUsagePage();
    }
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
    __walletsPage: null,
    __paymentMethodsPage: null,
    __transactionsPage: null,
    __usagePage: null,
    __paymentMethods: null,
    __transactionsTable: null,

    __addWalletsPage: function() {
      const title = this.tr("Credit Accounts");
      const iconSrc = "@MaterialIcons/account_balance_wallet/22";
      const walletsView = new osparc.desktop.wallets.WalletsView();
      walletsView.addListener("buyCredits", () => this.__openBuyCredits());
      const page = this.addTab(title, iconSrc, walletsView);
      return page;
    },

    __addPaymentMethodsPage: function() {
      const title = this.tr("Payment Methods");
      const iconSrc = "@FontAwesome5Solid/credit-card/22";
      const paymentMethods = this.__paymentMethods = new osparc.desktop.paymentMethods.PaymentMethods();
      const page = this.addTab(title, iconSrc, paymentMethods);
      return page;
    },

    __addTransactionsPage: function() {
      const title = this.tr("Transactions");
      const iconSrc = "@FontAwesome5Solid/exchange-alt/22";
      const transactions = this.__transactionsTable = new osparc.desktop.credits.Transactions();
      const page = this.addTab(title, iconSrc, transactions);
      return page;
    },

    __addUsagePage: function() {
      const title = this.tr("Usage");
      const iconSrc = "@FontAwesome5Solid/list/22";
      const usage = new osparc.desktop.credits.Usage();
      const page = this.addTab(title, iconSrc, usage);
      return page;
    },

    openWallets: function() {
      if (this.__walletsPage) {
        return this._openPage(this.__walletsPage);
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
      this._openPage(this.__paymentMethodsPage);
    },

    openTransactions: function(fetchTransactions = false) {
      if (fetchTransactions) {
        this.__transactionsTable.refresh();
        this._openPage(this.__transactionsPage);
      } else {
        this._openPage(this.__transactionsPage);
      }
    },

    openUsage: function() {
      this._openPage(this.__usagePage);
    }
  }
});
