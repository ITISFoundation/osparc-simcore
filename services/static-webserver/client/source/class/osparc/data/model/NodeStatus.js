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

    if (node.isDynamic()) {
      const progressSequence = new osparc.data.model.NodeProgressSequence();
      this.setProgressSequence(progressSequence);
    }
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
      event: "changeProgress",
      transform: "__transformProgress"
    },

    progressSequence: {
      check: "osparc.data.model.NodeProgressSequence",
      nullable: true,
      init: null
    },

    running: {
      check: ["UNKNOWN", "NOT_STARTED", "PUBLISHED", "PENDING", "WAITING_FOR_RESOURCES", "WAITING_FOR_CLUSTER", "STARTED", "RETRY", "SUCCESS", "FAILED", "ABORTED"],
      nullable: true,
      init: null,
      event: "changeRunning",
      apply: "__applyRunning"
    },

    interactive: {
      check: ["idle", "starting", "stopping", "pulling", "pending", "connecting", "ready", "failed", "deprecated", "retired"],
      nullable: true,
      init: null,
      event: "changeInteractive",
      apply: "__applyInteractive"
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

  statics: {
    getValidProgress: function(value) {
      if (value !== null && !Number.isNaN(value) && value >= 0 && value <= 100) {
        return Number.parseFloat(value.toFixed(4));
      }
      return 0;
    },

    isCompNodeReady: function(node) {
      if (node && node.isComputational()) {
        return node.getStatus().getRunning() === "SUCCESS" && node.getStatus().getOutput() === "up-to-date";
      }
      return true;
    },

    isComputationalRunning(node) {
      if (node && node.isComputational()) {
        return ["PUBLISHED", "WAITING_FOR_CLUSTER", "PENDING", "WAITING_FOR_RESOURCES", "STARTED"].includes(node.getStatus().getRunning());
      }
      return false;
    },

    doesCompNodeNeedRun: function(node) {
      if (node && node.isComputational()) {
        return (
          [
            "UNKNOWN",
            "NOT_STARTED",
            "FAILED",
            "ABORTED"
          ].includes(node.getStatus().getRunning()) ||
          [
            "not-available",
            "out-of-date"
          ].includes(node.getStatus().getOutput())
        );
      }
      return false;
    }
  },

  members: {
    __transformProgress: function(value) {
      const oldP = this.getProgress();
      if (this.getNode().isFilePicker() && oldP === 100 && value !== 0 && value !== 100) {
        // a NodeUpdated backend message could override the progress with an older value
        value = 100;
      }
      return value;
    },

    hasDependencies: function() {
      const dependencies = this.getDependencies();
      if (dependencies && dependencies.length) {
        return true;
      }
      return false;
    },

    __applyRunning: function(value) {
      if (value === "FAILED") {
        // ask why it failed
      }
      this.__recomputeOutput();
    },

    __applyInteractive: function(value) {
      if (value === "failed") {
        this.getProgressSequence().resetSequence();
      }
    },

    __recomputeOutput: function() {
      const compRunning = this.getRunning();
      const hasOutputs = this.getHasOutputs();
      const modified = this.getModified();
      const hasDependencies = this.hasDependencies();
      if (["PUBLISHED", "PENDING", "WAITING_FOR_RESOURCES", "WAITING_FOR_CLUSTER", "STARTED"].includes(compRunning)) {
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
      if (state == undefined || state === null) {
        return;
      }
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
      state["dependencies"] = this.getDependencies() ? this.getDependencies() : [];
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
