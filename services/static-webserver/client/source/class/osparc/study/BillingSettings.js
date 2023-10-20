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

qx.Class.define("osparc.study.BillingSettings", {
  extend: qx.ui.core.Widget,

  /**
   * @param studyData {Object} Object containing part or the entire serialized Study Data
   */
  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__studyData = studyData;

    this.__buildLayout();
  },

  members: {
    __studyData: null,

    __buildLayout: function() {
      this.__buildLastWalletGroup();
      this.__buildPricingUnitsGroup();
    },

    __buildLastWalletGroup: function() {
      const pricingUnitsLayout = osparc.study.StudyOptions.createGroupBox(this.tr("Credit Account"));

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const label = new qx.ui.basic.Label(this.tr("Select Credit Account"));
      hBox.add(label);

      const walletSelector = osparc.desktop.credits.Utils.createWalletSelector("read");
      hBox.add(walletSelector);

      pricingUnitsLayout.add(hBox);

      const params = {
        url: {
          studyId: this.__studyData["uuid"]
        }
      };
      osparc.data.Resources.fetch("studies", "getWallet", params)
        .then(wallet => {
          const walletFound = walletSelector.getSelectables().find(selectables => selectables.walletId === wallet["walletId"]);
          if (walletFound) {
            walletSelector.setSelection([walletFound]);
          } else {
            const label2 = new qx.ui.basic.Label(this.tr("You don't have access to the last used Credit Account"));
            hBox.add(label2);
          }
        });

      this._add(pricingUnitsLayout);
    },

    __buildPricingUnitsGroup: function() {
      const pricingUnitsLayout = osparc.study.StudyOptions.createGroupBox(this.tr("Tiers"));
      const pricingUnits = new osparc.study.StudyPricingUnits(this.__studyData);
      pricingUnitsLayout.add(pricingUnits);
      this._add(pricingUnitsLayout);
    }
  }
});
