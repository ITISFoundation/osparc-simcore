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
        case "wallets-card":
          control = this.__createOverviewCard("Wallet", "toWallets");
          this._add(control, {
            column: 0,
            row: 0
          });
          break;
        case "transactions-card":
          control = this.__createOverviewCard("Transactions", "toTransactions");
          this._add(control, {
            column: 1,
            row: 0
          });
          break;
        case "usage-card":
          control = this.__createOverviewCard("Usage", "toUsageOverview");
          this._add(control, {
            column: 0,
            row: 1,
            colSpan: 2
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("wallets-card");
      this.getChildControl("transactions-card");
      this.getChildControl("usage-card");
    },

    __createOverviewCard: function(cardName, signalName) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        minWidth: 200,
        minHeight: 200,
        padding: 10,
        backgroundColor: "background-main-1"
      });
      layout.getContentElement().setStyles({
        "border-radius": "4px"
      });

      const label = new qx.ui.basic.Label().set({
        value: cardName,
        font: "text-14"
      });
      layout.add(label);

      const goToButton = new qx.ui.form.Button().set({
        label: this.tr("Go to ") + cardName,
        width: 130,
        allowGrowX: false,
        alignX: "right"
      });
      goToButton.addListener("execute", () => this.fireEvent(signalName), this);
      layout.add(goToButton);

      return layout;
    }
  }
});
