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
  extend: qx.ui.basic.Atom,

  construct: function(wallet, shortWording) {
    this.base(arguments);

    this.set({
      font: "text-16",
      alignY: "middle"
      // icon: "@MaterialIcons/monetization_on/16",
      // iconPosition: "right"
    });

    if (wallet) {
      this.setWallet(wallet);
    }

    if (shortWording !== undefined) {
      this.setShortWording(shortWording);
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

    this.bind("shortWording", this, "label", {
      converter: () => this.__recomputeLabel()
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
    },

    shortWording: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeShortWording"
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
      let label = creditsAvailable;
      if (this.isShortWording()) {
        label += this.tr(" cr.");
      } else {
        label += this.tr(" credits");
      }
      return label;
    }
  }
});
