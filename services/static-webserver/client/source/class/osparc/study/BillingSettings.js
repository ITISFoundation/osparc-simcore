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
    __walletDebtButton: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credit-account-box":
          control = osparc.study.StudyOptions.createGroupBox(this.tr("Credit Account"));
          this._add(control);
          break;
        case "credit-account-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
            alignY: "middle"
          });
          this.getChildControl("credit-account-box").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      if (osparc.study.Utils.isInDebt(this.__studyData)) {
        this.__buildDebtMessage();
      }
      this.__buildWalletGroup();
      this.__buildPricingUnitsGroup();
    },

    __buildDebtMessage: function() {
      const studyAlias = osparc.product.Utils.getStudyAlias();
      let msg = this.tr(`This ${studyAlias} is currently Embargoed.`) + "<br>";
      msg += this.tr("Credits required to unblock it:") + "<br>";
      msg += -1*this.__studyData["debt"] + " " + this.tr("credits");
      const label = new qx.ui.basic.Label(msg).set({
        font: "text-14",
        rich: true,
        paddingBottom: 20,
      });
      this._add(label);
    },

    __buildWalletGroup: function() {
      const boxContent = this.getChildControl("credit-account-layout");
      boxContent.removeAll();

      const walletSelector = osparc.desktop.credits.Utils.createWalletSelector("read");
      boxContent.add(walletSelector);

      const paramsGet = {
        url: {
          studyId: this.__studyData["uuid"]
        }
      };
      osparc.data.Resources.fetch("studies", "getWallet", paramsGet)
        .then(wallet => {
          if (wallet) {
            const walletFound = walletSelector.getSelectables().find(selectables => selectables.walletId === wallet["walletId"]);
            if (walletFound) {
              walletSelector.setSelection([walletFound]);
              if (osparc.study.Utils.isInDebt(this.__studyData)) {
                this.__addPayDebtButton(wallet["walletId"]);
              }
            } else {
              const emptyItem = new qx.ui.form.ListItem("");
              emptyItem.walletId = null;
              walletSelector.add(emptyItem);
              walletSelector.setSelection([emptyItem]);
              const label = new qx.ui.basic.Label(this.tr("You don't have access to the last used Credit Account"));
              boxContent.add(label);
            }
          }
        })
        .finally(() => {
          walletSelector.addListener("changeSelection", e => {
            const selection = e.getData();
            if (selection.length) {
              const walletId = selection[0].walletId;
              if (walletId === null) {
                return;
              }
              if (osparc.study.Utils.isInDebt(this.__studyData)) {
                this.__addPayDebtButton(walletId);
              } else {
                this.__switchWallet(walletId);
              }
            }
          });
        });
    },

    __addPayDebtButton: function(walletId) {
      const boxContent = this.getChildControl("credit-account-layout");
      if (this.__walletDebtButton) {
        boxContent.remove(this.__walletDebtButton);
      }
      const wallet = osparc.desktop.credits.Utils.getWallet(walletId);
      if (wallet.getCreditsAvailable() > -1*this.__studyData["debt"]) {
        this.__walletDebtButton = new qx.ui.form.Button(this.tr("Pay with this Credit Account"));
      } else {
        this.__walletDebtButton = new qx.ui.form.Button(this.tr("Buy Credits"));
      }
      boxContent.add(this.__walletDebtButton);
    },

    __switchWallet: function(walletId) {
      const creditAccountLayout = this.getChildControl("credit-account-layout");
      creditAccountLayout.setEnabled(false);
      const paramsPut = {
        url: {
          studyId: this.__studyData["uuid"],
          walletId
        }
      };
      osparc.data.Resources.fetch("studies", "selectWallet", paramsPut)
        .then(() => {
          const msg = this.tr("Credit Account saved");
          osparc.FlashMessenger.getInstance().logAs(msg, "INFO");
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logAs(err.message, "ERROR");
        })
        .finally(() => {
          creditAccountLayout.setEnabled(true);
          this.__buildWalletGroup();
        });
    },

    __buildPricingUnitsGroup: function() {
      const pricingUnitsLayout = osparc.study.StudyOptions.createGroupBox(this.tr("Tiers"));
      const pricingUnits = new osparc.study.StudyPricingUnits(this.__studyData);
      pricingUnitsLayout.add(pricingUnits);
      this._add(pricingUnitsLayout);
    }
  }
});
