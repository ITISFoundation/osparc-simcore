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

    const atom = new qx.ui.basic.Atom().set({
      alignX: "right",
      font: "text-16"
    });
    this._add(atom);

    const progressBar = this.__progressBar = new qx.ui.core.Widget().set({
      allowGrowX: true,
      height: 4
    });
    this._add(progressBar);

    if (wallet) {
      this.setWallet(wallet);
    }

    this.addListener("changeCreditsAvailable", () => this.__recomputeProgressBar());
    this.__recomputeProgressBar();

    this.bind("creditsAvailable", atom, "label", {
      converter: () => this.__recomputeLabel()
    });

    this.bind("creditsAvailable", atom, "textColor", {
      converter: credits => this.self().creditsToColor(credits, "text")
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

  statics: {
    creditsToColor: function(credits, defaultColor = "text") {
      let color = defaultColor;
      if (credits < 0) {
        color = "danger-red";
      } else if (credits < 20) {
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
    __progressBar: null,

    __applyWallet: function(wallet) {
      if (wallet) {
        wallet.bind("creditsAvailable", this, "creditsAvailable");
      }
    },

    __recomputeProgressBar: function() {
      const credits = this.getCreditsAvailable();
      if (credits !== null) {
        const bgColor = this.self().creditsToColor(credits, "strong-main");
        const progress = this.self().normalizeCredits(credits);
        this.__progressBar.setBackgroundColor(bgColor);
        this.__progressBar.getContentElement().setStyles({
          width: progress + "%"
        });
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
