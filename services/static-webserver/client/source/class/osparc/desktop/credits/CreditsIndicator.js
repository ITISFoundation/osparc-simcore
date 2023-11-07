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

  construct: function(wallet = null) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.setWallet(wallet);

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

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credits-text":
          control = new qx.ui.basic.Label().set({
            alignX: "center",
            font: "text-16"
          });
          this._add(control);
          break;
        case "credits-bar":
          control = new qx.ui.core.Widget().set({
            height: 4
          });
          control.getContentElement().setStyles({
            "border-radius": "2px"
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
        const label = this.getChildControl("credits-text");
        label.set({
          value: credits === null ? "-" : osparc.desktop.credits.Utils.creditsToFixed(credits) + this.tr(" credits"),
          textColor: osparc.desktop.credits.Utils.creditsToColor(credits, "text")
        });

        const indicator = this.getChildControl("credits-bar");
        const progress = credits > 0 ? osparc.desktop.credits.Utils.normalizeCredits(credits) : 100; // make bar red
        const creditsColor = osparc.desktop.credits.Utils.creditsToColor(credits, "strong-main");
        const color1 = qx.theme.manager.Color.getInstance().resolve(creditsColor);
        const textColor = qx.theme.manager.Color.getInstance().resolve("text");
        const arr = qx.util.ColorUtil.stringToRgb(textColor);
        arr[3] = 0.5;
        const color2 = qx.util.ColorUtil.rgbToRgbString(arr);
        indicator.getContentElement().setStyles({
          background: `linear-gradient(90deg, ${color1} ${progress}%, ${color2} ${progress}%)`
        });
      }
    }
  }
});
