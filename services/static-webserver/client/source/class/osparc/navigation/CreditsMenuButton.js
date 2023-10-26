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
  extend: qx.ui.form.MenuButton,

  construct: function() {
    const menu = new qx.ui.menu.Menu().set({
      position: "top-right"
    });

    this.base(arguments, null, null, menu);

    this.set({
      font: "text-16",
      backgroundColor: "transparent",
      rich: true
    });

    this.getChildControl("label").set({
      textAlign: "center"
    });

    const preferencesSettings = osparc.Preferences.getInstance();
    this.__computeVisibility();
    preferencesSettings.addListener("changeWalletIndicatorVisibility", () => this.__computeVisibility());
    preferencesSettings.addListener("changeCreditsWarningThreshold", () => {
      this.__computeVisibility();
      this.__updateCredits();
    });

    const store = osparc.store.Store.getInstance();
    this.__contextWalletChanged(store.getContextWallet());
    store.addListener("changeContextWallet", () => this.__contextWalletChanged());


    const preferencesButton = new qx.ui.menu.Button(this.tr("Preferences"));
    preferencesButton.addListener("execute", () => osparc.desktop.preferences.PreferencesWindow.openWindow(), this);
    menu.add(preferencesButton);

    const billingCenterButton = new qx.ui.menu.Button(this.tr("Billing Center"));
    billingCenterButton.addListener("execute", () => {
      const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
      const myAccountWindow = osparc.desktop.credits.BillingCenterWindow.openWindow();
      if (walletsEnabled) {
        myAccountWindow.openOverview();
      }
    }, this);
    menu.add(billingCenterButton);

    osparc.utils.Utils.prettifyMenu(menu);
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
        currentUsage.addListener("changeUsedCredits", () => this.__updateCredits());
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

    __animate: function() {
      const desc = {
        duration: 500,
        timing: "ease-out",
        keyFrames: {
          0: {
            "opacity": 1
          },
          70: {
            "opacity": 0.8
          },
          100: {
            "opacity": 1
          }
        }
      };
      const label = this.getChildControl("credits-label");
      qx.bom.element.Animation.animate(label.getContentElement().getDomElement(), desc);
    },

    __updateCredits: function() {
      const store = osparc.store.Store.getInstance();
      const wallet = store.getContextWallet();
      if (wallet) {
        let text = "-";
        const currentUsage = this.getCurrentUsage();
        let used = null;
        if (currentUsage) {
          used = currentUsage.getUsedCredits();
        }
        const creditsLeft = wallet.getCreditsAvailable();
        if (creditsLeft !== null) {
          text = "<span style='font-size:13px;display:inline-block'>credits</span><br>";
          let creditsLeftText = osparc.desktop.credits.Utils.creditsToFixed(creditsLeft);
          if (used !== null) {
            creditsLeftText += " / -" + osparc.desktop.credits.Utils.creditsToFixed(used);
          }
          text += `<span>${creditsLeftText}</span>`;
        }
        this.set({
          label: text,
          textColor: osparc.desktop.credits.Utils.creditsToColor(creditsLeft, "text")
        });
      }
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
