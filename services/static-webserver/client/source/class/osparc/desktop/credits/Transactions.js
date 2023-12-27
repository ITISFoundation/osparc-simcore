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

qx.Class.define("osparc.desktop.credits.Transactions", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__params = {
      filters: {
        from: null,
        until: null
      }
    }

    const store = osparc.store.Store.getInstance();
    store.getGroupsMe()
      .then(personalGroup => {
        this.__personalWallet = store.getWallets().find(wallet => wallet.getOwner() === personalGroup.gid)
        this.__personalWalletId = this.__personalWallet.getWalletId()
        this.__buildLayout()
      });
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "transactions-table":
          control = new osparc.desktop.credits.TransactionsTable();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._removeAll();

      this.__introLabel = new qx.ui.basic.Label().set({
        value: this.tr("Top-up and refunds in US Dollars associated to your personal account show up here."),
        font: "text-14",
        rich: true,
        wrap: true
      });
      this._add(this.__introLabel);

      this.__dateFilters = new osparc.desktop.credits.DateFilters();
      this.__dateFilters.addListener("change", e => this.__saveFilters(e.getData()));
      this._add(this.__dateFilters);

      const wallet = this.__personalWallet;
      if (wallet && wallet.getMyAccessRights()["write"]) {
        const transactionsTable = this._createChildControlImpl("transactions-table");
        osparc.data.Resources.fetch("payments", "get")
          .then(transactions => {
            if ("data" in transactions) {
              transactionsTable.addData(transactions["data"]);
            }
          })
          .catch(err => console.error(err));
      } else {
        this._add(osparc.desktop.credits.Utils.getNoWriteAccessInformationLabel());
      }
    },

    refresh: function() {
      console.log(this.__params);
    },

    __saveFilters: function(filters) {
      this.__params = {
        ...this.__params,
        filters
      };
      this.refresh();
    }
  }
});
