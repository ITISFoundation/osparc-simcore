/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Ignacio Pascual (ignapas)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.ResourceInTableViewer", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this._buildLayout();
  },

  members: {
    _createChildControlImpl: function(id) {
      let layout;
      let control;
      switch (id) {
        case "intro-text":
          control = new qx.ui.basic.Label("Select a Credit Account:");
          this._add(control);
          break;
        case "wallet-selector-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._add(control);
          break;
        case "wallet-selector":
          control = new qx.ui.form.SelectBox().set({
            allowStretchX: false,
            width: 200
          });
          layout = this.getChildControl("wallet-selector-layout");
          layout.add(control);
          break;
        case "fetching-image":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/circle-notch/12",
            alignX: "center",
            alignY: "middle",
            visibility: "excluded"
          });
          control.getContentElement().addClass("rotate");
          layout = this.getChildControl("wallet-selector-layout");
          layout.add(control);
          break;
        case "filter-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._add(control);
          break;
        case "date-filters":
          control = new osparc.desktop.credits.DateFilters();
          control.addListener("change", e => {
            const table = this.getChildControl("table");
            table.getTableModel().setFilters(e.getData());
            table.getTableModel().reloadData();
          });
          layout = this.getChildControl("filter-layout");
          layout.add(control);
          break;
        case "export-button":
          control = new qx.ui.form.Button(this.tr("Export")).set({
            allowStretchY: false,
            alignY: "bottom",
          });
          control.addListener("execute", () => this._handleExport());
          layout = this.getChildControl("filter-layout");
          layout.add(control);
          break;
        case "reload-button":
          control = new qx.ui.form.Button(this.tr("Reload"), "@FontAwesome5Solid/sync-alt/14").set({
            allowStretchY: false,
            alignY: "bottom"
          });
          control.addListener("execute", () => {
            const table = this.getChildControl("table");
            table.getTableModel().reloadData();
          });
          layout = this.getChildControl("filter-layout");
          layout.add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      const introText = this.getChildControl("intro-text");
      const walletSelectBox = this.getChildControl("wallet-selector");
      this.getChildControl("fetching-image");

      const filterLayout = this.getChildControl("filter-layout");
      this.getChildControl("date-filters");
      filterLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      const exportButton = this.getChildControl("export-button");
      this.getChildControl("reload-button");

      walletSelectBox.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          const table = this.getChildControl("table");
          table.getTableModel().setWalletId(this._getSelectWalletId());
          table.getTableModel().reloadData();
        }
      });

      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
        const store = osparc.store.Store.getInstance();
        store.getWallets().forEach(wallet => {
          walletSelectBox.add(new qx.ui.form.ListItem(wallet.getName(), null, wallet));
        });
      } else {
        introText.setVisibility("excluded");
        walletSelectBox.setVisibility("excluded");
        exportButton.setVisibility("excluded");
        this.getChildControl("table");
      }
    },

    _getSelectWalletId: function() {
      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
        const walletSelectBox = this.getChildControl("wallet-selector");
        const selectedWallet = walletSelectBox.getSelection()[0].getModel();
        return selectedWallet.getWalletId();
      }
      return null;
    },

    _handleExport: function() {
      throw new Error("Abstract method called!");
    },
  }
});
