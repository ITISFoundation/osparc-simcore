/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.CreditsPerService", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.initDaysRange();
  },

  properties: {
    daysRange: {
      check: [1, 7, 30],
      nullable: false,
      init: 1,
      apply: "__populateList"
    }
  },

  members: {
    __populateList: function(nDays) {
      this._removeAll();

      const store = osparc.store.Store.getInstance();
      const contextWallet = store.getContextWallet();
      if (!contextWallet) {
        return;
      }
      const walletId = contextWallet.getWalletId();
      const loadingImage = new qx.ui.basic.Image("@FontAwesome5Solid/circle-notch/26").set({
        alignX: "center",
        padding: 6
      });
      loadingImage.getContentElement().addClass("rotate");
      this._add(loadingImage);

      const params = {
        "url": {
          walletId,
          "timePeriod": nDays
        }
      };
      osparc.data.Resources.fetch("resourceUsage", "getUsagePerService", params)
        .then(entries => {
          this._removeAll();
          if (entries) {
            let totalCredits = 0;
            entries.forEach(entry => totalCredits+= entry["osparc_credits"]);
            let datas = [];
            entries.forEach(entry => {
              datas.push({
                service: entry["service_key"],
                credits: -1*entry["osparc_credits"],
                percentage: 100*entry["osparc_credits"]/totalCredits,
              });
            });
            datas.sort((a, b) => b.percentage - a.percentage);
            // top 5 services
            datas = datas.slice(0, 5);
            datas.forEach(data => {
              const uiEntry = new osparc.desktop.credits.CreditsServiceListItem(data.service, data.credits, data.percentage);
              this._add(uiEntry);
            });
          }
        });
    }
  }
});
