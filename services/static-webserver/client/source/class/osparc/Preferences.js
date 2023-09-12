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

qx.Class.define("osparc.Preferences", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    preferredWalletId: {
      nullable: false,
      init: null,
      check: "Number",
      event: "changePreferredWalletId"
    },

    themeName: {
      nullable: false,
      init: {},
      check: "String",
      apply: "__applyThemeName"
    },

    // ---------------------------

    autoConnectPorts: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeAutoConnectPorts",
      apply: "__patchPreference"
    },

    confirmBackToDashboard: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmBackToDashboard",
      apply: "__patchPreference"
    },

    confirmDeleteStudy: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmDeleteStudy",
      apply: "__patchPreference"
    },

    confirmDeleteNode: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmDeleteNode",
      apply: "__patchPreference"
    },

    confirmStopNode: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmStopNode",
      apply: "__patchPreference"
    },

    snapNodeToGrid: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeSnapNodeToGrid",
      apply: "__patchPreference"
    }
  },

  statics: {
    patchPreference: function(preferenceId, value) {
      const params = {
        url: {
          preferenceId
        },
        data: {
          value
        }
      };
      return osparc.data.Resources.fetch("preferences", "patch", params);
    }
  },

  members: {
    __applyThemeName: function(themeName) {
      if (themeName && themeName !== qx.theme.manager.Meta.getInstance().getTheme().name) {
        const preferredTheme = qx.Theme.getByName(themeName);
        const themes = qx.Theme.getAll();
        if (preferredTheme && Object.keys(themes).includes(preferredTheme.name)) {
          qx.theme.manager.Meta.getInstance().setTheme(preferredTheme);

          if (osparc.auth.Manager.getInstance().isLoggedIn()) {
            this.self().patchPreference("themeName", preferredTheme.name);
          }
        }
      }
    },

    requestChangePreferredWalletId: function(walletId) {
      this.self().patchPreference("preferredWalletId", walletId)
        .then(() => {
          this.setPreferredWalletId(walletId);
          const wallets = osparc.store.Store.getInstance().getWallets();
          wallets.forEach(wallet => wallet.setPreferredWallet(wallet.getWalletId() === walletId));
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.logAs(err.message, "ERROR");
        });
    },

    __patchPreference: function(value, _, propName) {
      this.self().patchPreference(propName, value);
    }
  }
});
