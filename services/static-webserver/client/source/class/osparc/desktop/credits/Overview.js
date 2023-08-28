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
          control = this.__createOverviewCard("Wallets", content, "toWallets");
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
          const content = this.__createWalletsView();
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
        width: 130,
        allowGrowX: false,
        alignX: "right"
      });
      goToButton.addListener("execute", () => this.fireEvent(signalName), this);
      layout.add(goToButton);

      return layout;
    },

    __createWalletsView: function() {
      const grid = new qx.ui.layout.Grid(12, 8);
      const layout = new qx.ui.container.Composite(grid);

      const wallets = osparc.store.Store.getInstance().getWallets();
      const maxWallets = 5;
      for (let i=0; i<wallets.length && i<maxWallets; i++) {
        const wallet = wallets[i];

        // thumbnail or shared or not shared
        const thumbnail = new qx.ui.basic.Image().set({
          backgroundColor: "transparent",
          alignX: "center",
          alignY: "middle"
        });
        const value = wallet.getThumbnail();
        if (value) {
          thumbnail.setSource(value);
        } else if (wallet.getAccessRights() && wallet.getAccessRights().length > 1) {
          thumbnail.setSource(osparc.utils.Icons.organization(18));
        } else {
          thumbnail.setSource(osparc.utils.Icons.user(18));
        }
        layout.add(thumbnail, {
          column: 0,
          row: i
        });

        // indicator
        const progressBar = new osparc.desktop.credits.CreditsIndicatorWText(wallet, "horizontal").set({
          allowShrinkY: true
        });
        progressBar.getChildControl("credits-indicator").set({
          minWidth: 100
        });
        layout.add(progressBar, {
          column: 1,
          row: i
        });

        // favourite
        const starImage = new qx.ui.basic.Image().set({
          alignY: "middle"
        });
        wallet.bind("defaultWallet", starImage, "source", {
          converter: isDefault => isDefault ? "@FontAwesome5Solid/star/20" : "@FontAwesome5Regular/star/20"
        });
        wallet.bind("defaultWallet", starImage, "textColor", {
          converter: isDefault => isDefault ? "strong-main" : null
        });
        layout.add(starImage, {
          column: 2,
          row: i
        });
      }

      return layout;
    },

    __createTransactionsView: function() {
      const grid = new qx.ui.layout.Grid(12, 8);
      const layout = new qx.ui.container.Composite(grid);

      const entries = [[
        osparc.utils.Utils.formatDateAndTime(new Date()),
        10,
        0,
        "My Wallet",
        "Welcome to Sim4Life"
      ], [
        osparc.utils.Utils.formatDateAndTime(new Date()),
        50,
        125,
        "My Wallet",
        "A payment"
      ]];
      entries.forEach((entry, row) => {
        entry.forEach((data, column) => {
          const text = new qx.ui.basic.Label(data.toString()).set({
            font: "text-13"
          });
          layout.add(text, {
            row,
            column
          });
        });
      });
      return layout;
    }
  }
});
