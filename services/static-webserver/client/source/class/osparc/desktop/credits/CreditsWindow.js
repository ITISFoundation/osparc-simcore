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

  construct: function(walletsEnabled = false) {
    this.base(arguments, "credits", this.tr("Account"));

    this.__walletsEnabled = walletsEnabled;

    const viewWidth = walletsEnabled ? 1050 : 800;
    const viewHeight = walletsEnabled ? 700 : 600;

    this.set({
      layout: new qx.ui.layout.Grow(),
      modal: true,
      width: viewWidth,
      height: viewHeight,
      showMaximize: false,
      showMinimize: false,
      resizable: true,
      appearance: "service-window"
    });

    const tabViews = this.__tabsView = new qx.ui.tabview.TabView().set({
      barPosition: "left",
      contentPadding: 0
    });
    tabViews.getChildControl("bar").add(this.__getMiniProfileView());

    if (this.__walletsEnabled) {
      const overviewPage = this.__overviewPage = this.__getOverviewPage();
      tabViews.add(overviewPage);
    }

    const profilePage = this.__profilePage = this.__getProfilePage();
    tabViews.add(profilePage);

    const securityPage = this.__securityPage = this.__getSecurityPage();
    tabViews.add(securityPage);

    if (this.__walletsEnabled) {
      const walletsPage = this.__walletsPage = this.__getWalletsPage();
      tabViews.add(walletsPage);
    }

    if (this.__walletsEnabled) {
      const buyCreditsPage = this.__buyCreditsPage = this.__getBuyCreditsPage();
      tabViews.add(buyCreditsPage);
    }

    if (this.__walletsEnabled) {
      const transactionsPage = this.__transactionsPage = this.__getTransactionsPage();
      tabViews.add(transactionsPage);
    }

    if (osparc.data.Permissions.getInstance().canDo("usage.all.read")) {
      const usageOverviewPage = this.__usageOverviewPage = this.__getUsageOverviewPage();
      tabViews.add(usageOverviewPage);
    }

    this.add(tabViews);
  },

  statics: {
    openWindow: function(walletsEnabled = false) {
      const accountWindow = new osparc.desktop.credits.CreditsWindow(walletsEnabled);
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  },

  members: {
    __walletsEnabled: null,
    __tabsView: null,
    __overviewPage: null,
    __profilePage: null,
    __securityPage: null,
    __walletsPage: null,
    __buyCreditsPage: null,
    __transactionsPage: null,
    __usageOverviewPage: null,
    __buyCredits: null,
    __transactionsTable: null,

    __getMiniProfileView: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(8)).set({
        alignX: "center",
        maxWidth: 150
      });

      const authData = osparc.auth.Data.getInstance();
      const email = authData.getEmail();
      const img = new qx.ui.basic.Image().set({
        source: osparc.utils.Avatar.getUrl(email, 100),
        maxWidth: 80,
        maxHeight: 80,
        scale: true,
        decorator: new qx.ui.decoration.Decorator().set({
          radius: 30
        }),
        alignX: "center"
      });
      layout.add(img);

      const name = new qx.ui.basic.Label().set({
        font: "text-14",
        alignX: "center"
      });
      layout.add(name);
      authData.bind("firstName", name, "value", {
        converter: firstName => firstName + " " + authData.getLastName()
      });
      authData.bind("lastName", name, "value", {
        converter: lastName => authData.getFirstName() + " " + lastName
      });

      const emailLabel = new qx.ui.basic.Label(email).set({
        font: "text-13",
        alignX: "center"
      });
      layout.add(emailLabel);

      layout.add(new qx.ui.core.Spacer(15, 15), {
        flex: 1
      });

      return layout;
    },

    __getOverviewPage: function() {
      const title = this.tr("Overview");
      const iconSrc = "@FontAwesome5Solid/table/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const overview = new osparc.desktop.credits.Overview();
      overview.set({
        margin: 10
      });
      overview.addListener("toWallets", () => this.openWallets());
      overview.addListener("toTransactions", () => this.__openTransactions());
      overview.addListener("toUsageOverview", () => this.__openUsageOverview());
      page.add(overview);
      return page;
    },

    __getProfilePage: function() {
      const page = new osparc.desktop.credits.ProfilePage();
      page.showLabelOnTab();
      return page;
    },

    __getSecurityPage: function() {
      const page = new osparc.desktop.credits.SecurityPage();
      page.showLabelOnTab();
      const secBtn = page.getChildControl("button");
      osparc.utils.Utils.setIdToWidget(secBtn, "preferencesSecurityTabBtn");
      return page;
    },

    __getWalletsPage: function() {
      const title = this.tr("Wallets");
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

    __getBuyCreditsPage: function() {
      const title = this.tr("Buy Credits");
      const iconSrc = "@FontAwesome5Solid/dollar-sign/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const buyCredits = this.__buyCredits = new osparc.desktop.credits.BuyCredits();
      buyCredits.set({
        margin: 10
      });
      buyCredits.addListener("transactionSuccessful", e => {
        const {
          nCredits,
          totalPrice,
          walletName
        } = e.getData();
        this.__transactionsTable.addRow(nCredits, totalPrice, walletName);
        this.__openTransactions();
      }, this);
      page.add(buyCredits);
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

    __getUsageOverviewPage: function() {
      const title = this.tr("Usage Overview");
      const iconSrc = "@FontAwesome5Solid/list/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
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

    openOverview: function() {
      if (this.__overviewPage) {
        this.__openPage(this.__overviewPage);
      } else {
        // fallback
        this.__openPage(this.__profilePage);
      }
    },

    openWallets: function() {
      if (this.__walletsPage) {
        this.__openPage(this.__walletsPage);
      } else {
        // fallback
        this.__openPage(this.__profilePage);
      }
    },

    __openBuyCredits: function() {
      this.__openPage(this.__buyCreditsPage);
    },

    __openTransactions: function() {
      this.__openPage(this.__transactionsPage);
    },

    __openUsageOverview: function() {
      this.__openPage(this.__usageOverviewPage);
    }
  }
});
