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

    this.__buildLayout();
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
        case "activity-card": {
          const content = this.__createUsageView();
          control = this.__createOverviewCard("Last Activity", content, "All Activity", "toActivity");
          this._add(control);
          break;
        }
        case "transactions-card": {
          const content = this.__createTransactionsView();
          control = this.__createOverviewCard("Transactions", content, "All Transactions", "toTransactions");
          this._add(control);
          break;
        }
        case "usage-card": {
          const content = this.__createUsageView();
          control = this.__createOverviewCard("Settings", content, "Usage", "toUsageOverview");
          this._add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("wallets-card");
      this.getChildControl("transactions-card");
      this.getChildControl("usage-card");
    },

    __createOverviewCard: function(cardLabel, content, buttonLabel, signalName) {
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
      goToButton.addListener("execute", () => this.fireEvent(signalName), this);
      topLayout.add(goToButton);
      layout.add(topLayout);

      content.setPadding(5);
      layout.add(content, {
        flex: 1
      });

      return layout;
    },

    __createWalletsView: function() {
      const activeWallet = osparc.store.Store.getInstance().getActiveWallet();
      const preferredWallet = osparc.desktop.credits.Utils.getPreferredWallet();
      const wallet = activeWallet ? activeWallet : preferredWallet;
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

    __createTransactionsView: function() {
      const grid = new qx.ui.layout.Grid(12, 8);
      const layout = new qx.ui.container.Composite(grid);

      const headers = [
        "Date",
        "Price",
        "Credits",
        "Credit Account",
        "Comment"
      ];
      headers.forEach((header, column) => {
        const text = new qx.ui.basic.Label(header).set({
          font: "text-14"
        });
        layout.add(text, {
          row: 0,
          column
        });
      });

      osparc.data.Resources.fetch("payments", "get")
        .then(transactions => {
          if ("data" in transactions) {
            const maxTransactions = 4;
            transactions["data"].forEach((transaction, row) => {
              if (row < maxTransactions) {
                let walletName = null;
                if (transaction["walletId"]) {
                  const found = osparc.desktop.credits.Utils.getWallet(transaction["walletId"]);
                  if (found) {
                    walletName = found.getName();
                  }
                }
                const entry = [
                  osparc.utils.Utils.formatDateAndTime(new Date(transaction["createdAt"])),
                  transaction["priceDollars"].toFixed(2).toString(),
                  transaction["osparcCredits"].toFixed(2).toString(),
                  walletName,
                  transaction["comment"]
                ];
                entry.forEach((data, column) => {
                  const text = new qx.ui.basic.Label(data).set({
                    font: "text-13"
                  });
                  layout.add(text, {
                    row: row+1,
                    column
                  });
                });
                row++;
              }
            });
          }
        })
        .catch(err => console.error(err));

      return layout;
    },

    __createUsageView: function() {
      const grid = new qx.ui.layout.Grid(12, 8);
      const layout = new qx.ui.container.Composite(grid);

      const cols = osparc.desktop.credits.UsageTable.COLUMNS;
      const colNames = Object.values(cols).map(col => col.title);
      colNames.forEach((colName, column) => {
        const text = new qx.ui.basic.Label(colName).set({
          font: "text-14"
        });
        layout.add(text, {
          row: 0,
          column
        });
      });

      const params = {
        url: {
          offset: 0,
          limit: 4 // show only the last 4 usage
        }
      };
      osparc.data.Resources.fetch("resourceUsage", "getPage", params)
        .then(async datas => {
          const entries = await osparc.desktop.credits.UsageTable.respDataToTableData(datas);
          entries.forEach((entry, row) => {
            entry.forEach((data, column) => {
              const text = new qx.ui.basic.Label(data.toString()).set({
                font: "text-13"
              });
              layout.add(text, {
                row: row+1,
                column
              });
            });
          });
        });
      return layout;
    }
  }
});
