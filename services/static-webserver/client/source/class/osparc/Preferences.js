/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.Preferences", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
  },

  properties: {
    preferredWalletId: {
      nullable: false,
      init: null,
      check: "Object",
      event: "changePreferredWalletId"
    },

    themeName: {
      nullable: false,
      init: {},
      check: "String",
      apply: "__applyThemeName"
    },
    /*
    dontShowAnnouncements: {
      nullable: false,
      init: {},
      check: "Object"
    },

    serviceHits: {
      nullable: false,
      init: {},
      check: "Object"
    },
    */

    // ---------------------------

    autoConnectPorts: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeAutoConnectPorts",
      apply: "__savePreferences"
    },

    confirmBackToDashboard: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmBackToDashboard",
      apply: "__savePreferences"
    },

    confirmDeleteStudy: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmDeleteStudy",
      apply: "__savePreferences"
    },

    confirmDeleteNode: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmDeleteNode",
      apply: "__savePreferences"
    },

    confirmStopNode: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmStopNode",
      apply: "__savePreferences"
    },

    snapNodeToGrid: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeSnapNodeToGrid",
      apply: "__savePreferences"
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
      osparc.data.Resources.fetch("preferences", "patch", params);
    }
  },

  members: {
    __applyThemeName: function(...args) {
      console.log(args);
      const themeName = args[0];
      if (themeName && themeName !== qx.theme.manager.Meta.getInstance().getTheme().name) {
        const preferredTheme = qx.Theme.getByName(themeName);
        const themes = qx.Theme.getAll();
        if (preferredTheme && Object.keys(themes).includes(preferredTheme.name)) {
          qx.theme.manager.Meta.getInstance().setTheme(preferredTheme);
        }
      }
    },

    saveThemeName: function(value) {
      if (osparc.auth.Manager.getInstance().isLoggedIn()) {
        this.self().patchPreference("themeName", value);
      }
    },

    requestChangePreferredWalletId: function(walletId) {
      const params = {
        url: {
          preferenceId: "preferredWalletId"
        },
        data: {
          value: walletId
        }
      };
      osparc.data.Resources.fetch("preferences", "patch", params)
        .then(() => this.setPreferredWalletId(walletId))
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.logAs(err.message, "ERROR");
        });
    },

    __savePreferences: function(value, _, propName) {
      this.self().patchPreference(propName, value);
    }
  }
});
