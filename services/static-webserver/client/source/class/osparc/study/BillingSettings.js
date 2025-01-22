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
        case "wallet-selector":
          control = osparc.desktop.credits.Utils.createWalletSelector("read");
          this.getChildControl("credit-account-layout").add(control);
          break;
        case "pay-debt-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this.getChildControl("credit-account-layout").add(control);
          break;
        case "buy-credits-button":
          control = new qx.ui.form.Button(this.tr("Buy Credits"));
          this.getChildControl("pay-debt-layout").add(control);
          break;
        case "trasfer-debt-button":
          control = new qx.ui.form.Button(this.tr("Pay with this Credit Account"));
          this.getChildControl("pay-debt-layout").add(control);
          break;
        case "debt-explanation":
          control = new qx.ui.basic.Label();
          this.getChildControl("pay-debt-layout").add(control);
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
      const border = new qx.ui.decoration.Decorator().set({
        radius: 4,
        width: 1,
        style: "solid",
        color: "danger-red",
      });
      const studyAlias = osparc.product.Utils.getStudyAlias();
      let msg = this.tr(`This ${studyAlias} is currently Embargoed.<br>`);
      msg += this.tr("Last transaction:") + "<br>";
      msg += this.__studyData["debt"] + " " + this.tr("credits");
      const label = new qx.ui.basic.Label(msg).set({
        decorator: border,
        font: "text-14",
        rich: true,
        padding: 10,
        marginBottom: 5,
      });
      this._add(label);
    },

    __buildWalletGroup: function() {
      const boxContent = this.getChildControl("credit-account-layout");
      boxContent.removeAll();

      const walletSelector = this.getChildControl("wallet-selector");
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
                this.__addDebtLayout(wallet["walletId"]);
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
                this.__addDebtLayout(walletId);
              } else {
                this.__switchWallet(walletId);
              }
            }
          });
        });
    },

    __addDebtLayout: function(walletId) {
      const payDebtLayout = this.getChildControl("pay-debt-layout");
      payDebtLayout.removeAll();

      const wallet = osparc.desktop.credits.Utils.getWallet(walletId);
      const myWallets = osparc.desktop.credits.Utils.getMyWallets();
      if (myWallets.find(wllt => wllt === wallet)) {
        // It's my wallet
        // I just need to bring to positive numbers to unblock the embargoed studies
        const buyCredtisButton = this.getChildControl("buy-credits-button");
        buyCredtisButton.addListener("execute", () => console.log("open credits window"));
        this.getChildControl("debt-explanation").set({
          value: this.tr("You don't have access to the last used Credit Account")
        });
      } else {
        // It's a shared wallet
        // I need to make a credits transfer (debt) from it to the wallet that went negative
        const transferDebtButton = this.getChildControl("trasfer-debt-button");
        transferDebtButton.addListener("execute", () => console.log("open confirmation window"));
        this.getChildControl("debt-explanation").set({
          value: this.tr("You don't have access to the last used Credit Account")
        });
      }
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
