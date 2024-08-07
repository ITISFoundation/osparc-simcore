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
      const loadingImage = new qx.ui.basic.Image("@FontAwesome5Solid/circle-notch/26").set({
        alignX: "center",
        padding: 6
      });
      loadingImage.getContentElement().addClass("rotate");
      this._add(loadingImage);

      setTimeout(() => {
        this._removeAll();
        [{
          service: "simcore/services/comp/itis/sleeper",
          credits: nDays*30,
          percentage: 66
        }, {
          service: "simcore/services/dynamic/sim4life-8-0-0-dy",
          credits: nDays*20,
          percentage: 33
        }].forEach(entry => {
          const uiEntry = new osparc.desktop.credits.CreditsServiceListItem(entry.service, entry.credits, entry.percentage);
          this._add(uiEntry);
        });
      }, 1000);
    }
  }
});
