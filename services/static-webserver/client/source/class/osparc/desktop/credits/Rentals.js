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


qx.Class.define("osparc.desktop.credits.Rentals", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    const store = osparc.store.Store.getInstance();
    this.__userWallets = store.getWallets();

    this.__buildLayout()
  },

  members: {
    __buildLayout: function() {
      this._removeAll();

      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const lbl = new qx.ui.basic.Label("Select a Credit Account:");
      container.add(lbl);

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
      container.add(selectBoxContainer);

      const filterContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5))
      this.__dateFilters = new osparc.desktop.credits.DateFilters();
      this.__dateFilters.addListener("change", e => {
        this.__table.getTableModel().setFilters(e.getData())
        this.__table.getTableModel().reloadData()
      });
      filterContainer.add(this.__dateFilters);
      filterContainer.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this.__exportButton = new qx.ui.form.Button(this.tr("Export")).set({
        allowStretchY: false,
        alignY: "bottom"
      });
      this.__exportButton.addListener("execute", () => {
        this.__handleExport()
      });
      filterContainer.add(this.__exportButton);
      const refreshButton = new qx.ui.form.Button(this.tr("Reload"), "@FontAwesome5Solid/sync-alt/14").set({
        allowStretchY: false,
        alignY: "bottom"
      });
      refreshButton.addListener("execute", () => this.__table && this.__table.getTableModel().reloadData());
      filterContainer.add(refreshButton)
      container.add(filterContainer);

      this._add(container);

      walletSelectBox.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          this.__selectedWallet = selection[0].getModel()
          if (this.__table) {
            this.__table.getTableModel().setWalletId(this.__selectedWallet.getWalletId())
            this.__table.getTableModel().reloadData()
          } else {
            // qx: changeSelection is triggered after the first item is added to SelectBox
            this.__table = new osparc.desktop.credits.RentalsTable(this.__selectedWallet.getWalletId(), this.__dateFilters.getValue()).set({
              marginTop: 10
            })
            this.__table.getTableModel().bind("isFetching", this.__fetchingImg, "visibility", {
              converter: isFetching => isFetching ? "visible" : "excluded"
            })
            container.add(this.__table, { flex: 1 })
          }
        }
      });

      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
        this.__userWallets.forEach(wallet => {
          walletSelectBox.add(new qx.ui.form.ListItem(wallet.getName(), null, wallet));
        });
      } else {
        lbl.setVisibility("excluded")
        walletSelectBox.setVisibility("excluded")
        this.__exportButton.setVisibility("excluded")
        this.__table = new osparc.desktop.credits.RentalsTable(null, this.__dateFilters.getValue()).set({
          marginTop: 10
        })
        this.__table.getTableModel().bind("isFetching", this.__fetchingImg, "visibility", {
          converter: isFetching => isFetching ? "visible" : "excluded"
        })
        container.add(this.__table, { flex: 1 })
      }
    },
    __handleExport() {
      const reportUrl = new URL("/v0/services/-/rentals-report", window.location.origin)
      reportUrl.searchParams.append("wallet_id", this.__selectedWallet.getWalletId())
      reportUrl.searchParams.append("filters", JSON.stringify({ "started_at": this.__dateFilters.getValue() }))
      window.open(reportUrl, "_blank")
    }
  }
});
