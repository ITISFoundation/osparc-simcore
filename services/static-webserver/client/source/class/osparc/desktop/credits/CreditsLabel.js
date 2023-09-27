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

qx.Class.define("osparc.desktop.credits.CreditsLabel", {
  extend: qx.ui.basic.Label,

  construct: function(wallet) {
    this.base(arguments);

    this.set({
      alignY: "middle",
      font: "text-16"
    });
    this.bind("creditsAvailable", this, "value", {
      converter: val => val === null ? this.tr("Select Credit Account") : val + " " + this.tr("credits")
    });
    this.bind("creditsAvailable", this, "textColor", {
      converter: val => {
        if (val > 20) {
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
      event: "changeCreditsAvailable"
    }
  },

  members: {
    __applyWallet: function(wallet) {
      if (wallet) {
        wallet.bind("creditsAvailable", this, "creditsAvailable");
      }
    }
  }
});
