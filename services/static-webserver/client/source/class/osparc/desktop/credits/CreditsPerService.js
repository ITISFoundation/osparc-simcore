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
  },

  properties: {
    daysRange: {
      check: [1, 7, 30],
      nullable: false,
      init: null,
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
          if (entries && entries.length) {
            let totalCredits = 0;
            let totalHours = 0;
            entries.forEach(entry => {
              totalHours += entry["running_time_in_hours"]
              totalCredits+= parseFloat(entry["osparc_credits"])
            });
            let datas = [];
            entries.forEach(entry => {
              datas.push({
                service: entry["service_key"],
                credits: -1*parseFloat(entry["osparc_credits"]),
                hours: entry["running_time_in_hours"],
                percentageHours: totalHours ? 100*entry["running_time_in_hours"]/totalHours : 0,
                percentageCredits: totalCredits ? 100*parseFloat(entry["osparc_credits"])/totalCredits : 0,
              });
            });
            datas.sort((a, b) => {
              if (b.credits !== a.credits) {
                return b.credits - a.credits;
              }
              return b.hours - a.hours;
            });
            // top 5 services
            datas = datas.slice(0, 5);
            datas.forEach(data => {
              const uiEntry = new osparc.desktop.credits.CreditsServiceListItem(data.service, data.credits, data.hours, totalCredits === 0 ? data.percentageHours : data.percentageCredits);
              this._add(uiEntry);
            });
          } else {
            const nothingFound = new qx.ui.basic.Label(this.tr("No usage found")).set({
              font: "text-14"
            });
            this._add(nothingFound);
          }
        });
    }
  }
});
