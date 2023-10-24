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

  construct: function(wallet = null, bindToPreferences = false) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      wallet,
      bindToPreferences
    });

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
    },

    bindToPreferences: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeBindToPreferences",
      apply: "__applyBindToPreferences"
    }
  },

  statics: {
    WARNING_THRESHOLD: 700,

    creditsToColor: function(credits, defaultColor = "text") {
      let color = defaultColor;
      if (credits <= 0) {
        color = "danger-red";
      } else if (credits <= this.WARNING_THRESHOLD) {
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
        case "credits-text":
          control = new qx.ui.basic.Label().set({
            alignX: "center",
            allowGrowY: true,
            font: "text-16"
          });
          control.getContentElement().setStyles({
            "line-height": "33px"
          });
          this._add(control, {
            flex: 1
          });
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
          textColor: this.self().creditsToColor(credits, "text")
        });

        const indicator = this.getChildControl("credits-bar");
        const progress = this.self().normalizeCredits(credits);
        const bgColor = this.self().creditsToColor(credits, "strong-main");
        indicator.setBackgroundColor(bgColor);
        const ourBlue = qx.theme.manager.Color.getInstance().resolve("strong-main");
        const textColor = qx.theme.manager.Color.getInstance().resolve("text");
        const arr = qx.util.ColorUtil.stringToRgb(textColor);
        arr[3] = 0.5;
        const color2 = qx.util.ColorUtil.rgbToRgbString(arr);
        indicator.getContentElement().setStyles({
          background: `linear-gradient(90deg, ${ourBlue} ${progress}%, ${color2} ${progress}%)`
        });
        this.__computeVisibility();
      }
    },

    __applyBindToPreferences: function(bindToPreferences) {
      if (bindToPreferences) {
        const preferencesSettings = osparc.Preferences.getInstance();
        preferencesSettings.addListener("changeWalletIndicatorMode", () => this.__computeMode());
        this.__computeMode();
        preferencesSettings.addListener("changeWalletIndicatorVisibility", () => this.__computeVisibility());
      }
    },

    __computeMode: function() {
      if (this.getBindToPreferences()) {
        const preferencesSettings = osparc.Preferences.getInstance();
        switch (preferencesSettings.getWalletIndicatorMode()) {
          case "text":
            this.getChildControl("credits-text").show();
            this.getChildControl("credits-bar").exclude();
            break;
          case "bar":
            this.getChildControl("credits-text").exclude();
            this.getChildControl("credits-bar").show();
            break;
          default:
            this.getChildControl("credits-text").show();
            this.getChildControl("credits-bar").show();
            break;
        }
      }
    },

    __computeVisibility: function() {
      if (this.getBindToPreferences()) {
        const preferencesSettings = osparc.Preferences.getInstance();
        if (preferencesSettings.getWalletIndicatorVisibility() === "warning") {
          this.setVisibility(this.getCreditsAvailable() <= this.self().WARNING_THRESHOLD ? "visible" : "excluded");
        } else if (preferencesSettings.getWalletIndicatorVisibility() === "always") {
          this.setVisibility("visible");
        }
      }
    }
  }
});
