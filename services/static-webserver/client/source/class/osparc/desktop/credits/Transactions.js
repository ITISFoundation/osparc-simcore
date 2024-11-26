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

    const today = osparc.utils.Utils.formatDateYyyyMmDd(new Date())
    this.__params = {
      filters: {
        from: today,
        until: today
      }
    }

    const groupsStore = osparc.store.Groups.getInstance();
    const myGid = groupsStore.getMyGroupId()
    const store = osparc.store.Store.getInstance();
    this.__personalWallet = store.getWallets().find(wallet => wallet.getOwner() === myGid);
    this.__personalWalletId = this.__personalWallet.getWalletId();
    this.__buildLayout();
  },

  members: {
    __buildLayout: function() {
      this._removeAll();
      const introContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox())
      this.__introLabel = new qx.ui.basic.Label().set({
        value: this.tr("Top-up and refunds in US Dollars associated to your personal account show up here."),
        font: "text-14",
        rich: true,
        wrap: true
      });
      introContainer.add(this.__introLabel)
      introContainer.add(new qx.ui.core.Spacer(), { flex: 1 })
      const refreshButton = new qx.ui.form.Button(this.tr("Reload"), "@FontAwesome5Solid/sync-alt/14")
      refreshButton.addListener("execute", () => this.__table && this.__table.getTableModel().reloadData())
      introContainer.add(refreshButton)
      this._add(introContainer);

      // FEATURE TOGGLE
      // const filterContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox())
      // this.__dateFilters = new osparc.desktop.credits.DateFilters();
      // this.__dateFilters.addListener("change", e => this.__saveFilters(e.getData()));
      // filterContainer.add(this.__dateFilters);

      // filterContainer.add(new qx.ui.core.Spacer(), {
      //   flex: 1
      // });

      // this.__exportButton = new qx.ui.form.Button(this.tr("Export")).set({
      //   allowStretchY: false,
      //   alignY: "bottom"
      // });
      // this.__exportButton.addListener("execute", () => {
      //   console.log("export", this.__params);
      // });
      // filterContainer.add(this.__exportButton);

      // this._add(filterContainer);

      this.__table = new osparc.desktop.credits.TransactionsTable().set({
        marginTop: 10
      })
      if (this.__personalWallet && this.__personalWallet.getMyAccessRights()["write"]) {
        this._add(this.__table, { flex: 1 })
        this.__table.getTableModel().reloadData()
      } else {
        this._add(osparc.desktop.credits.Utils.getNoWriteAccessInformationLabel())
      }
    }
  }
});
