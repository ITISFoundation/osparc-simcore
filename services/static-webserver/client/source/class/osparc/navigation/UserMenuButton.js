/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.navigation.UserMenuButton", {
  extend: qx.ui.form.MenuButton,

  construct: function() {
    this.base(arguments);

    const authData = osparc.auth.Data.getInstance();

    const menu = new osparc.navigation.UserMenu();
    osparc.utils.Utils.setIdToWidget(menu, "userMenuMenu");
    this.set({
      width: 40,
      height: 40,
      font: "text-14",
      allowShrinkX: false,
      allowShrinkY: false,
      allowGrowX: false,
      allowGrowY: false,
      menu
    });

    this.getContentElement().setStyles({
      "border-radius": "20px"
    });
    this.getChildControl("icon").getContentElement().setStyles({
      "border-radius": "16px"
    });
    osparc.utils.Utils.setIdToWidget(this, "userMenuBtn");

    const store = osparc.store.Store.getInstance();
    this.__bindWalletToHalo();
    store.addListener("changeContextWallet", () => this.__bindWalletToHalo());

    const preferencesSettings = osparc.Preferences.getInstance();
    preferencesSettings.addListener("changeCreditsWarningThreshold", () => this.__updateHalloCredits());

    const userEmail = authData.getEmail() || "bizzy@itis.ethz.ch";
    const icon = this.getChildControl("icon");
    authData.bind("role", this, "icon", {
      converter: role => {
        if (["anonymous", "guest"].includes(role)) {
          icon.getContentElement().setStyles({
            "margin-left": "0px"
          });
          return "@FontAwesome5Solid/user-secret/28";
        }
        icon.getContentElement().setStyles({
          "margin-left": "-4px"
        });
        return osparc.utils.Avatar.getUrl(userEmail, 32);
      }
    });
  },

  statics: {
    openPreferences: function() {
      const preferencesWindow = osparc.desktop.preferences.PreferencesWindow.openWindow();
      return preferencesWindow;
    }
  },

  members: {
    __bindWalletToHalo: function() {
      const store = osparc.store.Store.getInstance();
      const contextWallet = store.getContextWallet();
      if (contextWallet) {
        this.__updateHalloCredits();
        contextWallet.addListener("changeCreditsAvailable", () => this.__updateHalloCredits());
      }
    },

    __updateHalloCredits: function() {
      const store = osparc.store.Store.getInstance();
      const contextWallet = store.getContextWallet();
      if (contextWallet) {
        const credits = contextWallet.getCreditsAvailable();
        if (credits !== null) {
          const progress = credits > 0 ? osparc.desktop.credits.Utils.normalizeCredits(credits) : 100; // make hallo red
          const creditsColor = osparc.desktop.credits.Utils.creditsToColor(credits, "strong-main");
          const color1 = qx.theme.manager.Color.getInstance().resolve(creditsColor);
          osparc.service.StatusUI.getStatusHalo(this, color1, progress);
        }
      }
    },

    populateMenu: function() {
      this.getMenu().populateMenu();
    },

    populateMenuCompact: function() {
      this.getMenu().populateMenuCompact();
    }
  }
});
