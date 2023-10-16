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

qx.Class.define("osparc.desktop.credits.Overview", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const grid = new qx.ui.layout.Grid(20, 20);
    grid.setColumnFlex(0, 1);
    grid.setColumnFlex(1, 1);
    this._setLayout(grid);

    this.__buildLayout();
  },

  events: {
    "buyCredits": "qx.event.type.Data",
    "toWallets": "qx.event.type.Event",
    "toTransactions": "qx.event.type.Event",
    "toUsageOverview": "qx.event.type.Event"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "wallets-card": {
          const content = this.__createWalletsView();
          const wallets = osparc.store.Store.getInstance().getWallets();
          control = this.__createOverviewCard(`Credit Accounts (${wallets.length})`, content, "toWallets");
          control.getChildren()[0].setValue(this.tr("Credits"));
          this._add(control, {
            column: 0,
            row: 0
          });
          break;
        }
        case "transactions-card": {
          const content = this.__createTransactionsView();
          control = this.__createOverviewCard("Transactions", content, "toTransactions");
          this._add(control, {
            column: 1,
            row: 0
          });
          break;
        }
        case "usage-card": {
          const content = this.__createUsageView();
          control = this.__createOverviewCard("Usage", content, "toUsageOverview");
          this._add(control, {
            column: 0,
            row: 1,
            colSpan: 2
          });
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

    __createOverviewCard: function(cardName, content, signalName) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        minWidth: 200,
        minHeight: 200,
        padding: 15,
        backgroundColor: "background-main-1"
      });
      layout.getContentElement().setStyles({
        "border-radius": "4px"
      });

      const title = new qx.ui.basic.Label().set({
        value: cardName,
        font: "text-14"
      });
      layout.add(title);

      content.setPadding(5);
      layout.add(content, {
        flex: 1
      });

      const goToButton = new qx.ui.form.Button().set({
        label: this.tr("Go to ") + cardName,
        allowGrowX: false,
        alignX: "right"
      });
      goToButton.addListener("execute", () => this.fireEvent(signalName), this);
      layout.add(goToButton);

      return layout;
    },

    __createWalletsView: function() {
      const activeWallet = osparc.store.Store.getInstance().getActiveWallet();
      const preferredWallet = osparc.desktop.credits.Utils.getPreferredWallet();
      const oneWallet = activeWallet ? activeWallet : preferredWallet;
      if (oneWallet) {
        // show one wallet
        return this.__showOneWallet(oneWallet);
      }
      // show some wallets
      return this.__showSomeWallets();
    },

    __showOneWallet: function(wallet) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

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
        alignY: "middle",
        maxWidth: 200
      });
      wallet.bind("name", walletName, "value");
      titleLayout.add(walletName);
      layout.add(titleLayout);

      const creditsIndicator = new osparc.desktop.credits.CreditsIndicator(wallet);
      layout.add(creditsIndicator);

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
    },

    __showSomeWallets: function() {
      const grid = new qx.ui.layout.Grid(12, 8);
      const layout = new qx.ui.container.Composite(grid);
      const maxWallets = 5;
      const wallets = osparc.store.Store.getInstance().getWallets();
      for (let i=0; i<wallets.length && i<maxWallets; i++) {
        let column = 0;

        const wallet = wallets[i];

        const maxSize = 20;
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
        layout.add(thumbnail, {
          column,
          row: i
        });
        column++;

        // name
        const walletName = new qx.ui.basic.Label().set({
          font: "text-14",
          maxWidth: 100
        });
        wallet.bind("name", walletName, "value");
        layout.add(walletName, {
          column,
          row: i
        });
        column++;

        // indicator
        const creditsIndicator = new osparc.desktop.credits.CreditsIndicator(wallet);
        layout.add(creditsIndicator, {
          column,
          row: i
        });
        column++;
      }

      return layout;
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

      const cols = osparc.resourceUsage.OverviewTable.COLUMNS;
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
          const entries = await osparc.resourceUsage.OverviewTable.respDataToTableData(datas);
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
