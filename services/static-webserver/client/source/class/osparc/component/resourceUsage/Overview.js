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

qx.Class.define("osparc.component.resourceUsage.Overview", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    const walletSelector = this.getChildControl("wallet-selector");
    walletSelector.exclude();
    osparc.desktop.credits.Utils.areWalletsEnabled()
      .then(walletsEnabled => {
        if (walletsEnabled) {
          walletSelector.show();
        }
      });

    const loadingImage = this.getChildControl("loading-image");
    loadingImage.show();
    const table = this.getChildControl("usage-table");
    table.exclude();

    this.__fetchData();
    walletSelector.addListener("changeSelection", () => {
      this.__prevRequestParams = null;
      this.__nextRequestParams = null;
      this.__fetchData();
    });
  },

  statics: {
    ITEMS_PER_PAGE: 15,

    popUpInWindow: function() {
      const title = qx.locale.Manager.tr("Usage Overview");
      const noteEditor = new osparc.component.resourceUsage.Overview();
      const viewWidth = 900;
      const viewHeight = 450;
      const win = osparc.ui.window.Window.popUpInWindow(noteEditor, title, viewWidth, viewHeight);
      win.center();
      win.open();
      return win;
    }
  },

  members: {
    __prevRequestParams: null,
    __nextRequestParams: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "wallet-selector": {
          control = osparc.desktop.credits.Utils.createWalletSelector("read", false, true).set({
            allowGrowX: false
          });
          // select "All wallets" by default
          control.getSelectables()[0].setLabel("All wallets");
          const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          const selectLabel = new qx.ui.basic.Label(this.tr("Select Wallet")).set({
            alignY: "middle"
          });
          layout.add(selectLabel);
          layout.add(control);
          this._add(layout);
          break;
        }
        case "loading-image":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/circle-notch/64",
            alignX: "center",
            alignY: "middle"
          });
          control.getContentElement().addClass("rotate");
          this._add(control);
          break;
        case "usage-table":
          control = new osparc.component.resourceUsage.OverviewTable().set({
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

    __fetchData: function(request) {
      const loadingImage = this.getChildControl("loading-image");
      loadingImage.show();
      const table = this.getChildControl("usage-table");
      table.exclude();

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
          loadingImage.exclude();
          table.show();
        });
    },

    __getPrevRequest: function() {
      const params = {
        url: {
          offset: osparc.component.resourceUsage.Overview.ITEMS_PER_PAGE,
          limit: osparc.component.resourceUsage.Overview.ITEMS_PER_PAGE
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
          limit: osparc.component.resourceUsage.Overview.ITEMS_PER_PAGE
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

      const walletSelector = this.getChildControl("wallet-selector");
      let walletId = walletSelector.getSelection()[0].walletId;
      if (walletId) {
        params.url["walletId"] = walletId.toString();
        return osparc.data.Resources.fetch("resourceUsagePerWallet", "getPage", params, undefined, options);
      }
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
