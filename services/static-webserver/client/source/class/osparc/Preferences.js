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
    },

    creditsWarningThreshold: {
      check: "Number",
      nullable: false,
      init: 200,
      event: "changeCreditsWarningThreshold",
      apply: "__patchPreference"
    },

    walletIndicatorVisibility: {
      check: ["always", "warning"],
      nullable: false,
      init: "warning",
      event: "changeWalletIndicatorVisibility",
      apply: "__patchPreference"
    },

    userInactivityThreshold: {
      check: "Number",
      nullable: false,
      init: 1800,
      event: "changeUserInactivityThreshold",
      apply: "__patchPreference"
    },

    lowDiskSpaceThreshold: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeLowDiskSpaceThreshold",
      apply: "__patchPreference"
    },

    jobConcurrencyLimit: {
      check: "Number",
      nullable: false,
      init: 1,
      event: "changeJobConcurrencyLimit",
      apply: "__patchPreference"
    },

    allowMetricsCollection: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeAllowMetricsCollection",
      apply: "__patchPreference"
    },

    twoFAPreference: {
      nullable: true,
      check: ["SMS", "EMAIL", "DISABLED"],
      init: "SMS",
      event: "changeTwoFAPreference",
      apply: "__patchPreference"
    },

    billingCenterUsageColumnOrder: {
      nullable: true,
      check: "Array",
      event: "changeBillingCenterUsageColumnOrder",
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
    },

    patchPreferenceField: function(preferenceId, preferenceField, newValue) {
      const preferencesSettings = osparc.Preferences.getInstance();

      const oldValue = preferencesSettings.get(preferenceId);
      if (newValue === oldValue) {
        return;
      }

      preferenceField.setEnabled(false);
      osparc.Preferences.patchPreference(preferenceId, newValue)
        .then(() => preferencesSettings.set(preferenceId, newValue))
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          preferenceField.setValue(oldValue);
        })
        .finally(() => preferenceField.setEnabled(true));
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
          const store = osparc.store.Store.getInstance();
          const wallets = store.getWallets();
          const walletFound = wallets.find(wallet => wallet.getWalletId() === walletId);
          if (walletFound) {
            store.setPreferredWallet(walletFound);
          }
          wallets.forEach(wallet => wallet.setPreferredWallet(wallet.getWalletId() === walletId));
          this.setPreferredWalletId(walletId);
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __patchPreference: function(value, old, propName) {
      // only patch if it changed
      if (value === old) {
        return;
      }
      this.self().patchPreference(propName, value);
    }
  }
});
