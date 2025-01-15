/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.desktop.credits.Purchases", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout()
  },

  members: {
    __buildLayout: function() {
      const lbl = new qx.ui.basic.Label(this.tr("Select a Credit Account:"));
      this._add(lbl);

      const selectBoxContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const walletSelectBox = new qx.ui.form.SelectBox().set({
        allowStretchX: false,
        width: 200
      });
      selectBoxContainer.add(walletSelectBox);
      this.__fetchingImg = new qx.ui.basic.Image().set({
        source: "@FontAwesome5Solid/circle-notch/12",
        alignX: "center",
        alignY: "middle",
        visibility: "excluded"
      });
      this.__fetchingImg.getContentElement().addClass("rotate");
      selectBoxContainer.add(this.__fetchingImg);
      this._add(selectBoxContainer);

      const filterContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5))
      this.__dateFilters = new osparc.desktop.credits.DateFilters();
      this.__dateFilters.addListener("change", e => {
        this.__table.getTableModel().setFilters(e.getData())
        this.__table.getTableModel().reloadData()
      });
      filterContainer.add(this.__dateFilters);
      const refreshButton = new qx.ui.form.Button(this.tr("Reload"), "@FontAwesome5Solid/sync-alt/14").set({
        allowStretchY: false,
        alignY: "bottom"
      });
      refreshButton.addListener("execute", () => this.__table && this.__table.getTableModel().reloadData());
      filterContainer.add(refreshButton)
      this._add(filterContainer);

      walletSelectBox.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          this.__selectedWallet = selection[0].getModel()
          if (this.__table) {
            this.__table.getTableModel().setWalletId(this.__selectedWallet.getWalletId())
            this.__table.getTableModel().reloadData()
          } else {
            // qx: changeSelection is triggered after the first item is added to SelectBox
            this.__table = new osparc.desktop.credits.PurchasesTable(this.__selectedWallet.getWalletId(), this.__dateFilters.getValue()).set({
              marginTop: 10
            })
            this.__table.getTableModel().bind("isFetching", this.__fetchingImg, "visibility", {
              converter: isFetching => isFetching ? "visible" : "excluded"
            })
            this._add(this.__table, { flex: 1 })
          }
        }
      });

      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
        const store = osparc.store.Store.getInstance();
        store.getWallets().forEach(wallet => {
          walletSelectBox.add(new qx.ui.form.ListItem(wallet.getName(), null, wallet));
        });
      } else {
        lbl.setVisibility("excluded")
        walletSelectBox.setVisibility("excluded")
        this.__table = new osparc.desktop.credits.PurchasesTable(null, this.__dateFilters.getValue()).set({
          marginTop: 10
        })
        this.__table.getTableModel().bind("isFetching", this.__fetchingImg, "visibility", {
          converter: isFetching => isFetching ? "visible" : "excluded"
        })
        this._add(this.__table, { flex: 1 })
      }
    },
  }
});
