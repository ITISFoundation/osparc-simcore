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
      init: false,
      check: "Boolean",
      event: "changeAutoConnectPorts"
    },

    autoOpenNode: {
      nullable: false,
      init: true,
      check: "Boolean",
      event: "changeAutoOpenNode"
    }
  }
});
