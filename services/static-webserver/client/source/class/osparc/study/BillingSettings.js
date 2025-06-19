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

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__studyData = studyData;

    this.__buildLayout();
  },

  events: {
    "debtPayed": "qx.event.type.Event",
    "closeWindow": "qx.event.type.Event",
  },

  members: {
    __studyData: null,
    __studyWalletId: null,
    __debtMessage: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credit-account-box":
          control = osparc.study.StudyOptions.createGroupBox(this.tr("Credit Account"));
          this._add(control);
          break;
        case "wallet-selector":
          control = osparc.desktop.credits.Utils.createWalletSelector("read");
          this.getChildControl("credit-account-box").add(control);
          break;
        case "pay-debt-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
            alignY: "middle",
          }));
          this.getChildControl("credit-account-box").add(control);
          break;
        case "debt-explanation":
          control = new qx.ui.basic.Label().set({
            rich: true,
            wrap: true,
          });
          this.getChildControl("pay-debt-layout").add(control);
          break;
        case "buy-credits-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Buy Credits"),
            icon: "@FontAwesome5Solid/dollar-sign/14",
            allowGrowX: false
          });
          this.getChildControl("pay-debt-layout").add(control);
          break;
        case "transfer-debt-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Transfer from this Credit Account"),
            icon: "@FontAwesome5Solid/exchange-alt/14",
            allowGrowX: false
          });
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
      msg += this.tr("Last charge:") + "<br>";
      msg += this.__studyData["debt"] + " " + this.tr("credits");
      const debtMessage = this.__debtMessage = new qx.ui.basic.Label(msg).set({
        decorator: border,
        font: "text-14",
        rich: true,
        padding: 10,
        marginBottom: 5,
      });
      this._add(debtMessage);
    },

    __buildWalletGroup: function() {
      const boxContent = this.getChildControl("credit-account-box");

      const walletSelector = this.getChildControl("wallet-selector");

      const paramsGet = {
        url: {
          studyId: this.__studyData["uuid"]
        }
      };
      osparc.data.Resources.fetch("studies", "getWallet", paramsGet)
        .then(wallet => {
          if (wallet) {
            this.__studyWalletId = wallet["walletId"];
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
          walletSelector.addListener("changeSelection", () => {
            const wallet = this.__getSelectedWallet();
            if (wallet) {
              const walletId = wallet.getWalletId();
              if (osparc.study.Utils.isInDebt(this.__studyData)) {
                this.__addDebtLayout(walletId);
              } else {
                this.__switchWallet(walletId);
              }
            }
          });
        });
    },

    __getSelectedWallet: function() {
      const walletSelector = this.getChildControl("wallet-selector");
      const selection = walletSelector.getSelection();
      if (selection.length) {
        const walletId = selection[0].walletId;
        if (walletId) {
          const wallet = osparc.desktop.credits.Utils.getWallet(walletId);
          if (wallet) {
            return wallet;
          }
        }
      }
      return null;
    },

    __getStudyWallet: function() {
      if (this.__studyWalletId) {
        const wallet = osparc.desktop.credits.Utils.getWallet(this.__studyWalletId);
        if (wallet) {
          return wallet;
        }
      }
      return null;
    },

    __addDebtLayout: function(walletId) {
      const payDebtLayout = this.getChildControl("pay-debt-layout");
      payDebtLayout.removeAll();

      const wallet = osparc.desktop.credits.Utils.getWallet(walletId);
      const myWallets = osparc.desktop.credits.Utils.getMyWallets();
      if (myWallets.find(wllt => wllt === wallet)) {
        // It's my wallet
        this._createChildControlImpl("debt-explanation").set({
          value: this.tr("Top up the Credit Account:<br>Purchase additional credits to restore a positive balance.")
        });
        const buyCreditsButton = this._createChildControlImpl("buy-credits-button");
        buyCreditsButton.addListener("execute", () => this.__openBuyCreditsWindow(), this);
      } else {
        // It's a shared wallet
        this._createChildControlImpl("debt-explanation").set({
          value: this.tr("Transfer credits from another Account:<br>Use this Credit Account to cover the negative balance.")
        });
        const transferDebtButton = this._createChildControlImpl("transfer-debt-button");
        transferDebtButton.addListener("execute", () => this.__transferCredits(), this);
      }
    },

    __openBuyCreditsWindow: function() {
      const wallet = this.__getSelectedWallet();
      if (wallet) {
        osparc.desktop.credits.Utils.getPaymentMethods(wallet.getWalletId())
          .then(paymentMethods => {
            const {
              buyCreditsWidget
            } = osparc.desktop.credits.Utils.openBuyCredits(paymentMethods);
            buyCreditsWidget.addListener("completed", () => {
              // at this point we can assume that the study got unblocked
              this.__debtPayed();
            })
          });
      }
    },

    __transferCredits: function() {
      const originWallet = this.__getSelectedWallet();
      const destWallet = this.__getStudyWallet();
      let msg = this.tr("A credits transfer will be initiated to cover the negative balance:");
      msg += "<br>- " + this.tr("Credits to transfer: ") + -1*this.__studyData["debt"];
      msg += "<br>- " + this.tr("From: ") + originWallet.getName();
      msg += "<br>- " + this.tr("To: ") + destWallet.getName();
      const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
        confirmText: this.tr("Transfer"),
      });
      confirmationWin.open();
      confirmationWin.addListener("close", () => {
        if (confirmationWin.getConfirmed()) {
          this.__doTransferCredits();
        }
      }, this);
    },

    __doTransferCredits: function() {
      const wallet = this.__getSelectedWallet();
      const params = {
        url: {
          studyId: this.__studyData["uuid"],
          walletId: wallet.getWalletId(),
        },
        data: {
          amount: this.__studyData["debt"],
        }
      };
      osparc.data.Resources.fetch("studies", "payDebt", params)
        .then(() => {
          // at this point we can assume that the study got unblocked
          this.__debtPayed();
          // also switch the study's wallet to this one
          this.__switchWallet(wallet.getWalletId());
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __debtPayed: function() {
      delete this.__studyData["debt"];
      osparc.store.Store.getInstance().setStudyDebt(this.__studyData["uuid"], 0);
      this.fireEvent("debtPayed");
      if (this.__debtMessage) {
        this._remove(this.__debtMessage);
      }
      this.getChildControl("pay-debt-layout").removeAll();
    },

    __switchWallet: function(walletId) {
      const creditAccountBox = this.getChildControl("credit-account-box");
      creditAccountBox.setEnabled(false);
      const paramsPut = {
        url: {
          studyId: this.__studyData["uuid"],
          walletId
        }
      };
      osparc.data.Resources.fetch("studies", "selectWallet", paramsPut)
        .then(() => {
          this.__studyWalletId = walletId;
          const msg = this.tr("Credit Account saved");
          osparc.FlashMessenger.logAs(msg, "INFO");
        })
        .catch(err => {
          if ("status" in err && err["status"] == 402) {
            osparc.study.Utils.extractDebtFromError(this.__studyData["uuid"], err);
          }
          osparc.FlashMessenger.logError(err);
          this.fireEvent("closeWindow");
        })
        .finally(() => {
          creditAccountBox.setEnabled(true);
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
