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
  extend: qx.ui.basic.Atom,

  construct: function(wallet) {
    this.base(arguments);

    this.set({
      font: "text-16",
      allowGrowX: false
    });

    if (wallet) {
      this.setWallet(wallet);
    }

    this.bind("creditsAvailable", this, "label", {
      converter: () => this.__recomputeLabel()
    });

    this.bind("creditsAvailable", this, "textColor", {
      converter: val => {
        if (val > 20) {
          return "text";
        } else if (val > 0.1) {
          return "warning-yellow";
        }
        return "danger-red";
      }
    });
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
    },

    __recomputeLabel: function() {
      const creditsAvailable = this.getCreditsAvailable();
      if (creditsAvailable === null) {
        return "-";
      }
      return osparc.desktop.credits.Utils.creditsToFixed(creditsAvailable) + this.tr(" credits");
    }
  }
});
