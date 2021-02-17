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
 *  In order to keep Node's Status separated from its more static data,
 * this class stores it.
 */

qx.Class.define("osparc.data.model.NodeStatus", {
  extend: qx.core.Object,

  construct: function() {
    this.base(arguments);
  },

  properties: {
    progress: {
      check: "Number",
      init: 0,
      event: "changeProgress"
    },

    running: {
      check: ["UNKNOWN", "NOT_STARTED", "PUBLISHED", "PENDING", "STARTED", "RETRY", "SUCCESS", "FAILED", "ABORTED"],
      nullable: true,
      event: "changeRunning"
    },

    interactive: {
      check: ["idle", "starting", "pulling", "pending", "connecting", "ready", "failed"],
      nullable: true,
      event: "changeInteractive"
    },

    dependencies: {
      check: "Array",
      nullable: true,
      event: "changeDependencies"
    },

    modified: {
      check: "Boolean",
      nullable: true,
      event: "changeModified"
    }
  }
});
