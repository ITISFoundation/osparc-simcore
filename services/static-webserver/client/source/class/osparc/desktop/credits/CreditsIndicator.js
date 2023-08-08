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

qx.Class.define("osparc.desktop.credits.CreditsIndicator", {
  extend: qx.ui.indicator.ProgressBar,

  construct: function(wallet, supportTap = false) {
    this.base(arguments);

    this.set({
      maximum: 1,
      width: 50,
      maxHeight: 20,
      minHeight: 10,
      allowGrowY: false,
      alignY:"middle"
    });

    this.bind("value", this.getChildControl("progress"), "backgroundColor", {
      converter: val => {
        if (val > 0.4) {
          return "strong-main";
        } else if (val > 0.1) {
          return "warning-yellow";
        }
        return "danger-red";
      }
    });

    if (wallet) {
      this.setWallet(wallet);
    }

    if (supportTap) {
      this.set({
        cursor: "pointer"
      });
      this.addListener("tap", () => {
        const creditsWindow = osparc.desktop.credits.CreditsWindow.openWindow();
        creditsWindow.openWallets();
      }, this);
    }
  },

  properties: {
    wallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      event: "changeWallet",
      apply: "__applyWallet"
    },

    creditsAvailable: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeCredits",
      apply: "__applyCreditsAvailable"
    }
  },

  statics: {
    convertCreditsToIndicatorValue: function(credits) {
      const logBase = (n, base) => Math.log(n) / Math.log(base);

      let normalized = logBase(credits, 10000) + 0.01;
      normalized = Math.min(Math.max(normalized, 0), 1);
      return normalized;
    }
  },

  members: {
    __applyWallet: function(wallet) {
      if (wallet) {
        wallet.bind("creditsAvailable", this, "creditsAvailable");
        wallet.bind("creditsAvailable", this, "toolTipText", {
          converter: val => wallet.getName() + ": " + val + " credits left"
        });
      }
    },

    __applyCreditsAvailable: function(creditsAvailable) {
      if (creditsAvailable !== null) {
        this.setValue(this.self().convertCreditsToIndicatorValue(creditsAvailable));

        if (creditsAvailable <= 0) {
          this.setBackgroundColor("danger-red");
        } else {
          this.resetBackgroundColor();
        }

        let tttext = creditsAvailable + " " + this.tr("credits left");
        if (this.getWallet()) {
          tttext = this.getWallet().getName() + ": " + tttext;
        }
        this.setToolTipText(tttext);
      }
    }
  }
});
