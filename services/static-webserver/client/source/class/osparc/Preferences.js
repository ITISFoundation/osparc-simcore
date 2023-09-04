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
    autoConnectPorts: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeAutoConnectPorts"
    },

    confirmBackToDashboard: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmBackToDashboard"
    },

    confirmDeleteStudy: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmDeleteStudy"
    },

    confirmDeleteNode: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmDeleteNode"
    },

    confirmStopNode: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeConfirmStopNode"
    },

    snapNodeToGrid: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeSnapNodeToGrid"
    },

    // ---------------------------
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
    preferredWalletId: {
      nullable: false,
      init: null,
      check: "Object",
      event: "changePreferredWalletId"
    },

    themeName: {
      nullable: false,
      init: {},
      check: "String"
    }
  },

  members: {
    saveThemeName: function(value) {
      const params = {
        url: {
          preferenceId: "themeName"
        },
        data: {
          value
        }
      };
      osparc.data.Resources.fetch("preferences", "patch", params);
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
    }
  }
});
