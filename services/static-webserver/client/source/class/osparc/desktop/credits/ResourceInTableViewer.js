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
          control.getChildControl("arrow").syncAppearance(); // force sync to show the arrow
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
          control = new osparc.filter.DateFilters();
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
          control.addListener("execute", () => this.reloadData());
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
          console.log("Reload Data: previous cache:", table.getTableModel().getCacheContent());
          table.getTableModel().reloadData();
        }
      });

      if (osparc.store.StaticInfo.isBillableProduct()) {
        const store = osparc.store.Store.getInstance();
        const contextWallet = store.getContextWallet();
        let preselectItem = null;
        store.getWallets().forEach(wallet => {
          const listItem = new qx.ui.form.ListItem(wallet.getName(), null, wallet);
          walletSelectBox.add(listItem);
          if (contextWallet && wallet.getWalletId() === contextWallet.getWalletId()) {
            preselectItem = listItem;
          }
        });
        if (preselectItem) {
          walletSelectBox.setSelection([preselectItem]);
        }
      } else {
        introText.setVisibility("excluded");
        walletSelectBox.setVisibility("excluded");
        exportButton.setVisibility("excluded");
        this.getChildControl("table");
      }
    },

    _getSelectWalletId: function() {
      if (osparc.store.StaticInfo.isBillableProduct()) {
        const walletSelectBox = this.getChildControl("wallet-selector");
        const selectedWallet = walletSelectBox.getSelection()[0].getModel();
        return selectedWallet.getWalletId();
      }
      return null;
    },

    reloadData: function() {
      const table = this.getChildControl("table");
      table.getTableModel().reloadData();
    },

    _handleExport: function() {
      throw new Error("Abstract method called!");
    },
  }
});
