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

qx.Class.define("osparc.desktop.credits.Summary", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const wallet = osparc.desktop.credits.Utils.getContextWallet();
    this.setContextWallet(wallet);
  },

  properties: {
    contextWallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: false,
      apply: "__buildLayout"
    }
  },

  events: {
    "buyCredits": "qx.event.type.Data",
    "toWallets": "qx.event.type.Event",
    "toActivity": "qx.event.type.Event"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "wallets-card": {
          const content = this.__createWalletsView();
          if (content) {
            const wallets = osparc.store.Store.getInstance().getWallets();
            control = this.__createOverviewCard(this.tr("Credits Balance"), content, `All Credit Accounts (${wallets.length})`, "toWallets");
            this._add(control);
          }
          break;
        }
        case "settings-card": {
          const content = this.__createSettingsView();
          const wallet = this.getContextWallet();
          control = this.__createOverviewCard(this.tr("Settings"), content, this.tr("Credit Options"), "buyCredits", {
            walletId: wallet ? wallet.getWalletId() : null
          });
          this._add(control);
          break;
        }
        case "activity-card": {
          const content = this.__createActivityView();
          control = this.__createOverviewCard(this.tr("Last Activity"), content, this.tr("All Activity"), "toActivity");
          this._add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("wallets-card");
      this.getChildControl("settings-card");
      this.getChildControl("activity-card");
    },

    __createOverviewCard: function(cardLabel, content, buttonLabel, signalName, signalData) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        padding: 15,
        backgroundColor: "background-main-1"
      });
      layout.getContentElement().setStyles({
        "border-radius": "4px"
      });

      const topLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const title = new qx.ui.basic.Label().set({
        value: cardLabel,
        font: "text-14",
        allowGrowX: true
      });
      topLayout.add(title, {
        flex: 1
      });

      const goToButton = new qx.ui.form.Button().set({
        label: buttonLabel,
        allowGrowX: false,
        alignX: "right"
      });
      goToButton.addListener("execute", () => signalData ? this.fireDataEvent(signalName, signalData) : this.fireEvent(signalName), this);
      topLayout.add(goToButton);
      layout.add(topLayout);

      content.setPadding(5);
      layout.add(content, {
        flex: 1
      });

      return layout;
    },

    __createWalletsView: function() {
      const wallet = this.getContextWallet();
      if (wallet) {
        // show one wallet
        const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

        const titleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
          alignY: "middle"
        });
        const maxSize = 24;
        // thumbnail or shared or not shared
        const thumbnail = new qx.ui.basic.Image().set({
          backgroundColor: "transparent",
          alignX: "center",
          alignY: "middle",
          scale: true,
          allowShrinkX: true,
          allowShrinkY: true,
          maxHeight: maxSize,
          maxWidth: maxSize
        });
        const value = wallet.getThumbnail();
        if (value) {
          thumbnail.setSource(value);
        } else if (wallet.getAccessRights() && wallet.getAccessRights().length > 1) {
          thumbnail.setSource(osparc.utils.Icons.organization(maxSize-4));
        } else {
          thumbnail.setSource(osparc.utils.Icons.user(maxSize-4));
        }
        titleLayout.add(thumbnail);

        // name
        const walletName = new qx.ui.basic.Label().set({
          font: "text-14",
          alignY: "middle"
        });
        wallet.bind("name", walletName, "value");
        titleLayout.add(walletName);
        layout.add(titleLayout);

        // credits indicator
        const creditsIndicator = new osparc.desktop.credits.CreditsIndicator(wallet);
        layout.add(creditsIndicator);

        // buy button
        const buyButton = new qx.ui.form.Button().set({
          label: this.tr("Buy Credits"),
          icon: "@FontAwesome5Solid/dollar-sign/16",
          maxHeight: 30,
          alignY: "middle",
          allowGrowX: false,
          height: 25
        });
        const myAccessRights = wallet.getMyAccessRights();
        buyButton.setEnabled(Boolean(myAccessRights && myAccessRights["write"]));
        buyButton.addListener("execute", () => this.fireDataEvent("buyCredits", {
          walletId: wallet.getWalletId()
        }), this);
        layout.add(buyButton);

        return layout;
      }
      return null;
    },

    __createSettingsView: function() {
      const wallet = this.getContextWallet();
      if (wallet && wallet.getMyAccessRights()["write"]) {
        const grid = new qx.ui.layout.Grid(20, 10);
        grid.setColumnAlign(0, "right", "middle");
        const layout = new qx.ui.container.Composite(grid);

        const t1t = new qx.ui.basic.Label(this.tr("Automatic Payment")).set({
          font: "text-14"
        });
        layout.add(t1t, {
          row: 0,
          column: 0
        });
        const t1v = new qx.ui.basic.Label().set({
          value: "Off",
          font: "text-14"
        });
        layout.add(t1v, {
          row: 0,
          column: 1
        });

        const t2t = new qx.ui.basic.Label(this.tr("Monthly Spending Limit")).set({
          font: "text-14"
        });
        layout.add(t2t, {
          row: 1,
          column: 0
        });
        const t2v = new qx.ui.basic.Label().set({
          font: "text-14"
        });
        layout.add(t2v, {
          row: 1,
          column: 1
        });

        const t3t = new qx.ui.basic.Label(this.tr("Payment Method")).set({
          font: "text-14"
        });
        layout.add(t3t, {
          row: 2,
          column: 0
        });
        const t3v = new qx.ui.basic.Label().set({
          font: "text-14"
        });
        layout.add(t3v, {
          row: 2,
          column: 1
        });

        wallet.bind("autoRecharge", t1v, "value", {
          converter: arData => arData["enabled"] ? this.tr("On") : this.tr("Off")
        });
        wallet.bind("autoRecharge", t2v, "value", {
          converter: arData => arData["enabled"] ? (arData["topUpAmountInUsd"]*arData["topUpCountdown"]) + " US$" : null
        });
        wallet.bind("autoRecharge", t3v, "value", {
          converter: arData => arData["enabled"] ? arData["paymentMethodId"] : null
        });

        return layout;
      }
      return osparc.desktop.credits.Utils.getNoWriteAccessLabel();
    },

    __createActivityView: function() {
      const grid = new qx.ui.layout.Grid(12, 8);
      const layout = new qx.ui.container.Composite(grid);

      const cols = osparc.desktop.credits.ActivityTable.COLUMNS;
      const colNames = Object.values(cols).map(col => col.title);
      colNames.forEach((colName, column) => {
        const text = new qx.ui.basic.Label(colName).set({
          font: "text-13"
        });
        layout.add(text, {
          row: 0,
          column
        });
      });

      const wallet = this.getContextWallet();
      if (wallet) {
        const walletId = wallet.getWalletId();
        const params = {
          url: {
            walletId: walletId,
            offset: 0,
            limit: 10
          }
        };
        Promise.all([
          osparc.data.Resources.fetch("resourceUsagePerWallet", "getPage", params),
          osparc.data.Resources.fetch("payments", "get")
        ])
          .then(responses => {
            const usages = responses[0];
            const transactions = responses[1]["data"];
            const activities1 = osparc.desktop.credits.ActivityTable.usagesToActivities(usages);
            // Filter out some transactions
            const filteredTransactions = transactions.filter(transaction => transaction["completedStatus"] !== "FAILED" && transaction["walletId"] === walletId);
            const activities2 = osparc.desktop.credits.ActivityTable.transactionsToActivities(filteredTransactions);
            const activities = activities1.concat(activities2);
            activities.sort((a, b) => new Date(b["date"]).getTime() - new Date(a["date"]).getTime());

            const maxRows = 6;
            const entries = osparc.desktop.credits.ActivityTable.respDataToTableData(activities);
            entries.forEach((entry, row) => {
              if (row >= maxRows) {
                return;
              }
              entry.forEach((data, column) => {
                const text = new qx.ui.basic.Label(data.toString()).set({
                  font: "text-14"
                });
                layout.add(text, {
                  row: row+1,
                  column
                });
              });
            });
          });
      }

      return layout;
    }
  }
});
