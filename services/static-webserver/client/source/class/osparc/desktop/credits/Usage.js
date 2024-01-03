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

qx.Class.define("osparc.desktop.credits.Usage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    const store = osparc.store.Store.getInstance();
    this.__userWallets = store.getWallets();

    this.__buildLayout()
  },

  statics: {
    ITEMS_PER_PAGE: 15
  },

  members: {
    __prevRequestParams: null,
    __nextRequestParams: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "usage-table":
          control = new osparc.desktop.credits.UsageTable().set({
            height: (this.self().ITEMS_PER_PAGE*20 + 40)
          });
          this._add(control);
          break;
        case "page-buttons":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
            allowGrowX: true,
            alignX: "center",
            alignY: "middle"
          });
          this._add(control);
          break;
        case "prev-page-button": {
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/chevron-left/12",
            allowGrowX: false
          });
          control.addListener("execute", () => this.__fetchData(this.__getPrevRequest()));
          const pageButtons = this.getChildControl("page-buttons");
          pageButtons.add(control);
          break;
        }
        case "current-page-label": {
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            textAlign: "center",
            alignY: "middle"
          });
          const pageButtons = this.getChildControl("page-buttons");
          pageButtons.add(control);
          break;
        }
        case "next-page-button": {
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/chevron-right/12",
            allowGrowX: false
          });
          control.addListener("execute", () => this.__fetchData(this.__getNextRequest()));
          const pageButtons = this.getChildControl("page-buttons");
          pageButtons.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._removeAll();

      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const lbl = new qx.ui.basic.Label("Select a credit account:");
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
      const filterContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox())
      this.__dateFilters = new osparc.desktop.credits.DateFilters();
      this.__dateFilters.addListener("change", e => console.log(e.getData()));
      filterContainer.add(this.__dateFilters);
      filterContainer.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this.__exportButton = new qx.ui.form.Button(this.tr("Export")).set({
        allowStretchY: false,
        alignY: "bottom"
      });
      this.__exportButton.addListener("execute", () => {
        console.log("export");
      });
      filterContainer.add(this.__exportButton);
      container.add(filterContainer);
      this._add(container);
      walletSelectBox.addListener("changeSelection", e => {
        if (walletSelectBox.getSelection().length) {
          const selectedWallet = walletSelectBox.getSelection()[0].getModel();
          this.__selectedWallet = selectedWallet;
          this.__fetchData();
        }
      });
      this.__userWallets.forEach(wallet => {
        walletSelectBox.add(new qx.ui.form.ListItem(wallet.getName(), null, wallet));
      });
    },

    __fetchData: function(request) {
      this.__fetchingImg.show();

      if (request === undefined) {
        request = this.__getNextRequest();
      }
      request
        .then(resp => {
          const data = resp["data"];
          this.__setData(data);
          this.__prevRequestParams = resp["_links"]["prev"];
          this.__nextRequestParams = resp["_links"]["next"];
          this.__evaluatePageButtons(resp);
        })
        .finally(() => {
          this.__fetchingImg.exclude();
        });
    },

    __getPrevRequest: function() {
      const params = {
        url: {
          offset: this.self().ITEMS_PER_PAGE,
          limit: this.self().ITEMS_PER_PAGE
        }
      };
      if (this.__prevRequestParams) {
        params.url.offset = osparc.utils.Utils.getParamFromURL(this.__prevRequestParams, "offset");
        params.url.limit = osparc.utils.Utils.getParamFromURL(this.__prevRequestParams, "limit");
      }
      return this.__getCommonRequest(params);
    },

    __getNextRequest: function() {
      const params = {
        url: {
          offset: 0,
          limit: this.self().ITEMS_PER_PAGE
        }
      };
      if (this.__nextRequestParams) {
        params.url.offset = osparc.utils.Utils.getParamFromURL(this.__nextRequestParams, "offset");
        params.url.limit = osparc.utils.Utils.getParamFromURL(this.__nextRequestParams, "limit");
      }
      return this.__getCommonRequest(params);
    },

    __getCommonRequest: function(params) {
      const options = {
        resolveWResponse: true
      };

      const selectedWallet = this.__selectedWallet;
      if (selectedWallet) {
        const walletId = selectedWallet.getWalletId();
        params.url["walletId"] = walletId.toString();
        return osparc.data.Resources.fetch("resourceUsagePerWallet", "getPage", params, undefined, options);
      }
      // Usage supports the non wallet enabled products
      return osparc.data.Resources.fetch("resourceUsage", "getPage", params, undefined, options);
    },

    __setData: function(data) {
      const table = this.getChildControl("usage-table");
      table.addData(data);
    },

    __evaluatePageButtons:function(resp) {
      this.getChildControl("prev-page-button").setEnabled(Boolean(this.__prevRequestParams));
      this.getChildControl("current-page-label").setValue(((resp["_meta"]["offset"]/this.self().ITEMS_PER_PAGE)+1).toString());
      this.getChildControl("next-page-button").setEnabled(Boolean(this.__nextRequestParams));
    }
  }
});
