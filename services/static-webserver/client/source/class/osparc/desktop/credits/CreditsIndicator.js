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
  extend: qx.ui.core.Widget,

  construct: function(wallet) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    if (wallet) {
      this.setWallet(wallet);
    }

    this.addListener("changeCreditsAvailable", () => this.__updateCredits());
    this.__updateCredits();
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
      init: null,
      nullable: false,
      event: "changeCreditsAvailable",
      apply: "__updateCredits"
    }
  },

  statics: {
    creditsToColor: function(credits, defaultColor = "text") {
      let color = defaultColor;
      if (credits <= 0) {
        color = "danger-red";
      } else if (credits <= 20) {
        color = "warning-yellow";
      }
      return color;
    },

    normalizeCredits: function(credits) {
      const logBase = (n, base) => Math.log(n) / Math.log(base);

      let normalized = logBase(credits, 10000) + 0.01;
      normalized = Math.min(Math.max(normalized, 0), 1);
      return normalized * 100;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credits-label":
          control = new qx.ui.basic.Label().set({
            alignX: "center",
            font: "text-16"
          });
          this._add(control);
          break;
        case "credits-indicator":
          control = new qx.ui.core.Widget().set({
            height: 5
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyWallet: function(wallet) {
      if (wallet) {
        wallet.bind("creditsAvailable", this, "creditsAvailable");
      }
    },

    __updateCredits: function() {
      const credits = this.getCreditsAvailable();
      if (credits !== null) {
        const label = this.getChildControl("credits-label");
        label.set({
          value: credits === null ? "-" : osparc.desktop.credits.Utils.creditsToFixed(credits) + this.tr(" credits"),
          textColor: this.self().creditsToColor(credits, "text")
        });

        const indicator = this.getChildControl("credits-indicator");
        const progress = this.self().normalizeCredits(credits);
        const bgColor = this.self().creditsToColor(credits, "strong-main");
        indicator.setBackgroundColor(bgColor);
        indicator.getContentElement().setStyles({
          minWidth: parseInt(progress) + "%",
          maxWidth: parseInt(progress) + "%"
        });
      }
    }
  }
});
