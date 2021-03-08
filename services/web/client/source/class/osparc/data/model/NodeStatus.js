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
      init: null,
      event: "changeRunning"
    },

    interactive: {
      check: ["idle", "starting", "pulling", "pending", "connecting", "ready", "failed"],
      nullable: true,
      init: null,
      event: "changeInteractive"
    },

    dependencies: {
      check: "Array",
      nullable: true,
      init: null,
      event: "changeDependencies",
      apply: "__applyDependencies"
    },

    hasOutputs: {
      check: "Boolean",
      init: false
    },

    modified: {
      check: "Boolean",
      nullable: true,
      init: null,
      event: "changeModified",
      apply: "__applyModified"
    }
  },

  members: {
    __hasDependencies: function() {
      const dependencies = this.getDependencies();
      if (dependencies && dependencies.length) {
        return true;
      }
      return false;
    },

    __applyDependencies: function() {
      this.__applyModified(this.__hasDependencies());
    },

    __applyModified: function(modified) {
      if (this.getHasOutputs()) {
        this.setModified(modified || this.__hasDependencies());
      } else {
        this.setModified(null);
      }
    }
  }
});
