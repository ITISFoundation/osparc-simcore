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

qx.Class.define("osparc.navigation.CreditsMenuButton", {
  extend: qx.ui.form.Button,

  construct: function() {
    this.base(arguments);

    this.set({
      font: "text-16",
      padding: 1,
      paddingLeft: 8,
      paddingRight: 8,
      marginTop: 4,
      marginBottom: 4,
      rich: true
    });

    this.getChildControl("label").set({
      textAlign: "right"
    });
    this.getContentElement().setStyle("line-height", 1.2);

    const preferencesSettings = osparc.Preferences.getInstance();
    preferencesSettings.addListener("changeWalletIndicatorVisibility", () => this.__computeVisibility());
    preferencesSettings.addListener("changeCreditsWarningThreshold", () => this.__updateCredits());

    const store = osparc.store.Store.getInstance();
    this.__contextWalletChanged(store.getContextWallet());
    store.addListener("changeContextWallet", () => this.__contextWalletChanged());

    this.addListener("execute", () => {
      const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
      if (walletsEnabled) {
        osparc.desktop.credits.BillingCenterWindow.openWindow();
      }
    }, this);
  },

  properties: {
    currentUsage: {
      check: "osparc.desktop.credits.CurrentUsage",
      init: null,
      nullable: true,
      apply: "__applyCurrentUsage"
    }
  },

  members: {
    __applyCurrentUsage: function(currentUsage) {
      if (currentUsage) {
        currentUsage.addListener("changeUsedCredits", () => {
          this.__updateCredits();
        });
      }
    },

    __contextWalletChanged: function() {
      const store = osparc.store.Store.getInstance();
      const wallet = store.getContextWallet();
      if (wallet) {
        this.__updateCredits();
        wallet.addListener("changeCreditsAvailable", () => this.__updateCredits());
      }
    },

    __updateCredits: function() {
      const store = osparc.store.Store.getInstance();
      const wallet = store.getContextWallet();
      if (wallet) {
        let text = "-";
        const creditsLeft = wallet.getCreditsAvailable();
        if (creditsLeft !== null) {
          text = "<span style='font-size:12px;display:inline-block'>CREDITS</span><br>";
          let nCreditsText = "";
          nCreditsText += osparc.desktop.credits.Utils.creditsToFixed(creditsLeft);
          text += `<span>${nCreditsText}</span>`;
        }
        this.set({
          label: text,
          textColor: osparc.desktop.credits.Utils.creditsToColor(creditsLeft, "text")
        });
      }
      this.__computeVisibility();
    },

    __computeVisibility: function() {
      const store = osparc.store.Store.getInstance();
      const preferencesSettings = osparc.Preferences.getInstance();
      if (preferencesSettings.getWalletIndicatorVisibility() === "warning") {
        const wallet = store.getContextWallet();
        if (wallet) {
          this.setVisibility(wallet.getCreditsAvailable() <= preferencesSettings.getCreditsWarningThreshold() ? "visible" : "excluded");
        }
      } else if (preferencesSettings.getWalletIndicatorVisibility() === "always") {
        this.setVisibility("visible");
      }
    }
  }
});
