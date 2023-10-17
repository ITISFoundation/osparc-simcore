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

qx.Class.define("osparc.desktop.credits.Activity", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.getChildControl("wallet-selector-title");
    const walletSelector = this.getChildControl("wallet-selector");
    const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
    this.getChildControl("wallet-selector-layout").setVisibility(walletsEnabled ? "visible" : "excluded");

    const loadingImage = this.getChildControl("loading-image");
    loadingImage.show();
    const table = this.getChildControl("activity-table");
    table.exclude();

    this.__fetchData();
    walletSelector.addListener("changeSelection", () => {
      this.__prevUsageRequestParams = null;
      this.__nextUsageRequestParams = null;
      this.__fetchData();
    });
  },

  statics: {
    ITEMS_PER_PAGE: 15
  },

  members: {
    __prevUsageRequestParams: null,
    __nextUsageRequestParams: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "wallet-selector-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          this._add(control);
          break;
        case "wallet-selector-title": {
          control = new qx.ui.basic.Label(this.tr("Select Credit Account")).set({
            alignY: "middle"
          });
          const layout = this.getChildControl("wallet-selector-layout");
          layout.add(control);
          break;
        }
        case "wallet-selector": {
          control = osparc.desktop.credits.Utils.createWalletSelector("read").set({
            allowGrowX: false
          });
          const layout = this.getChildControl("wallet-selector-layout");
          layout.add(control);
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
        case "activity-table":
          control = new osparc.desktop.credits.ActivityTable().set({
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
          control.addListener("execute", () => this.__fetchData(this.__getNextUsageRequest()));
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
      const table = this.getChildControl("activity-table");
      table.exclude();

      if (request === undefined) {
        request = this.__getNextUsageRequest();
      }
      Promise.all([
        request,
        osparc.data.Resources.fetch("payments", "get")
      ])
        .then(responses => {
          const usagesResp = responses[0];
          const usages = usagesResp["data"];
          const transactions = responses[1]["data"];
          const activities1 = osparc.desktop.credits.ActivityTable.usagesToActivities(usages);
          // Filter out some transactions
          const walletId = this.__getSelectedWalletId();
          const filteredTransactions = transactions.filter(transaction => transaction["completedStatus"] !== "FAILED" && transaction["walletId"] === walletId);
          const activities2 = osparc.desktop.credits.ActivityTable.transactionsToActivities(filteredTransactions);
          const activities = activities1.concat(activities2);
          activities.sort((a, b) => new Date(b["date"]).getTime() - new Date(a["date"]).getTime());
          this.__setData(activities);

          this.__prevUsageRequestParams = usagesResp["_links"]["prev"];
          this.__nextUsageRequestParams = usagesResp["_links"]["next"];
          this.__evaluatePageButtons(usagesResp);
        })
        .finally(() => {
          loadingImage.exclude();
          table.show();
        });
    },

    __getPrevRequest: function() {
      const params = {
        url: {
          offset: this.self().ITEMS_PER_PAGE,
          limit: this.self().ITEMS_PER_PAGE
        }
      };
      if (this.__prevUsageRequestParams) {
        params.url.offset = osparc.utils.Utils.getParamFromURL(this.__prevUsageRequestParams, "offset");
        params.url.limit = osparc.utils.Utils.getParamFromURL(this.__prevUsageRequestParams, "limit");
      }
      return this.__getUsageCommonRequest(params);
    },

    __getNextUsageRequest: function() {
      const params = {
        url: {
          offset: 0,
          limit: this.self().ITEMS_PER_PAGE
        }
      };
      if (this.__nextUsageRequestParams) {
        params.url.offset = osparc.utils.Utils.getParamFromURL(this.__nextUsageRequestParams, "offset");
        params.url.limit = osparc.utils.Utils.getParamFromURL(this.__nextUsageRequestParams, "limit");
      }
      return this.__getUsageCommonRequest(params);
    },

    __getSelectedWalletId: function() {
      const walletSelector = this.getChildControl("wallet-selector");
      const walletSelection = walletSelector.getSelection();
      return walletSelection && walletSelection.length ? walletSelection[0].walletId : null;
    },

    __getUsageCommonRequest: function(params) {
      const options = {
        resolveWResponse: true
      };

      const walletId = this.__getSelectedWalletId();
      if (walletId) {
        params.url["walletId"] = walletId.toString();
        return osparc.data.Resources.fetch("resourceUsagePerWallet", "getPage", params, undefined, options);
      }
      return null;
    },

    __setData: function(data) {
      const table = this.getChildControl("activity-table");
      table.addData(data);
    },

    __evaluatePageButtons:function(resp) {
      // this is not correct because we are populating the table with two different resources
      this.getChildControl("prev-page-button").setEnabled(Boolean(this.__prevUsageRequestParams));
      this.getChildControl("current-page-label").setValue(((resp["_meta"]["offset"]/this.self().ITEMS_PER_PAGE)+1).toString());
      this.getChildControl("next-page-button").setEnabled(Boolean(this.__nextUsageRequestParams));
    }
  }
});
