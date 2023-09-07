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

qx.Class.define("osparc.desktop.preferences.Preferences", {
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

    preferredWalletId: {
      nullable: false,
      init: 4, // required until we have the Preferences
      check: "Number"
    }
  }
});
