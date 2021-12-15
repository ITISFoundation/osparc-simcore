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

  construct: function(node) {
    this.base(arguments);

    this.setNode(node);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false
    },

    progress: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeProgress"
    },

    running: {
      check: ["UNKNOWN", "NOT_STARTED", "PUBLISHED", "PENDING", "STARTED", "RETRY", "SUCCESS", "FAILED", "ABORTED"],
      nullable: true,
      init: null,
      event: "changeRunning",
      apply: "__recomputeOutput"
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
      apply: "__recomputeOutput"
    },

    modified: {
      check: "Boolean",
      nullable: true,
      init: null,
      event: "changeModified",
      apply: "__recomputeOutput"
    },

    output: {
      check: ["not-available", "busy", "up-to-date", "out-of-date"],
      nullable: false,
      init: "not-available",
      event: "changeOutput"
    },

    hasOutputs: {
      check: "Boolean",
      init: false
    }
  },

  members: {
    hasDependencies: function() {
      const dependencies = this.getDependencies();
      if (dependencies && dependencies.length) {
        return true;
      }
      return false;
    },

    __recomputeOutput: function() {
      const compRunning = this.getRunning();
      const hasOutputs = this.getHasOutputs();
      const modified = this.getModified();
      const hasDependencies = this.hasDependencies();
      if (["PUBLISHED", "PENDING", "STARTED"].includes(compRunning)) {
        this.setOutput("busy");
      } else if ([null, false].includes(hasOutputs)) {
        this.setOutput("not-available");
      } else if (hasOutputs && (modified || hasDependencies)) {
        this.setOutput("out-of-date");
      } else if (hasOutputs && !modified) {
        this.setOutput("up-to-date");
      } else {
        console.error("Unknown output state");
      }
    },

    setState: function(state) {
      if ("dependencies" in state) {
        this.setDependencies(state.dependencies);
      }
      if ("currentStatus" in state && this.getNode().isComputational()) {
        // currentStatus is only applicable to computational services
        this.setRunning(state.currentStatus);
      }
      if ("modified" in state) {
        if (this.getHasOutputs()) {
          // File Picker can't have a modified output
          this.setModified((state.modified || this.hasDependencies()) && !this.getNode().isFilePicker());
        } else {
          this.setModified(null);
        }
      }
    },

    serialize: function() {
      const state = {};
      state["dependencies"] = this.getDepencies() ? this.getDepencies() : [];
      if (this.getNode().isComputational()) {
        state["currentStatus"] = this.getRunning();
      }
      state["modified"] = null;
      // File Picker can't have a modified output
      if (this.getHasOutputs() && !this.getNode().isFilePicker()) {
        state["modified"] = this.hasDependencies();
      }
    }
  }
});
