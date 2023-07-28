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

qx.Class.define("osparc.desktop.credits.CreditsIndicatorWText", {
  extend: qx.ui.core.Widget,

  construct: function(wallet) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("credits-indicator");
    this.getChildControl("credits-text");

    if (wallet) {
      this.setWallet(wallet);
    }
  },

  properties: {
    wallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      event: "changeWallet"
    },

    credits: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeCredits"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credits-indicator":
          control = new osparc.desktop.credits.CreditsIndicator();
          this.bind("wallet", control, "wallet");
          this._add(control);
          break;
        case "credits-text":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this.bind("credits", control, "value", {
            converter: wallet => wallet ? wallet.getCredits() + " " + this.tr("credits left") : this.tr("Select Wallet")
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyWallet: function(wallet) {
      if (wallet) {
        wallet.bind("credits", this, "credits");
      }
    }
  }
});
