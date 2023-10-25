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
      backgroundColor: "transparent"
    });

    const store = osparc.store.Store.getInstance();
    const preferencesSettings = osparc.Preferences.getInstance();

    const computeVisibility = () => {
      if (preferencesSettings.getWalletIndicatorVisibility() === "warning") {
        const wallet = store.getContextWallet();
        if (wallet) {
          this.setVisibility(wallet.getCreditsAvailable() <= preferencesSettings.getCreditsWarningThreshold() ? "visible" : "excluded");
        }
      } else if (preferencesSettings.getWalletIndicatorVisibility() === "always") {
        this.setVisibility("visible");
      }
    };
    computeVisibility();
    preferencesSettings.addListener("changeWalletIndicatorVisibility", () => computeVisibility());
    preferencesSettings.addListener("changeCreditsWarningThreshold", () => computeVisibility());

    const updateContextWallet = wallet => {
      if (wallet) {
        wallet.bind("creditsAvailable", this, "label", {
          converter: credits => osparc.desktop.credits.Utils.creditsToFixed(credits) + " credits"
        });
      }
    };

    updateContextWallet(store.getContextWallet());
    store.addListener("changeContextWallet", e => updateContextWallet(e.getData()));


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
  }
});
