/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Julian Querido (jsaq007)

************************************************************************ */

/**
 * The progress sequence of a dynamic service is as follows:
 *
 * [CLUSTER_UP_SCALING]
 * [SIDECARS_PULLING]
 * [SERVICE_OUTPUTS_PULLING, SERVICE_STATE_PULLING, SERVICE_IMAGES_PULLING] (notice the parallelism here)
 * [SERVICE_CONTAINERS_STARTING]
 * [SERVICE_INPUTS_PULLING] (when this happens, the frontend has already loaded the service and is displaying it to the user) I would still keep it as is, when we decide to make inputs pulling part of the boot sequence this will be helpful.
 *
 * This class provides different widgets that render the progress status
 *
 */


qx.Class.define("osparc.data.model.NodeProgressSequence", {
  extend: qx.core.Object,

  construct: function() {
    this.base(arguments);

    this.__initLayout();
  },

  properties: {
    overallProgress: {
      check: "Number",
      init: 0,
      nullable: false,
      apply: "__applyOverallProgress"
    },

    clusterUpScaling: {
      check: "Object",
      init: {
        progressLabel: qx.locale.Manager.tr("Waiting ..."),
        value: 0
      },
      nullable: false,
      apply: "__applyClusterUpScaling"
    },

    sidecarPulling: {
      check: "Object",
      init: {
        progressLabel: qx.locale.Manager.tr("Waiting ..."),
        value: 0
      },
      nullable: false,
      apply: "__applySidecarPulling"
    },

    outputsPulling: {
      check: "Object",
      init: {
        progressLabel: qx.locale.Manager.tr("Waiting ..."),
        value: 0
      },
      nullable: false,
      apply: "__applyOutputsPulling"
    },

    statePulling: {
      check: "Object",
      init: {
        progressLabel: qx.locale.Manager.tr("Waiting ..."),
        value: 0
      },
      nullable: false,
      apply: "__applyStatePulling"
    },

    imagesPulling: {
      check: "Object",
      init: {
        progressLabel: qx.locale.Manager.tr("Waiting ..."),
        value: 0
      },
      nullable: false,
      apply: "__applyImagesPulling"
    },

    startingSoftware: {
      check: "Object",
      init: {
        progressLabel: qx.locale.Manager.tr("Waiting ..."),
        value: 0
      },
      nullable: false,
      apply: "__applyStartingSoftware"
    },

    inputsPulling: {
      check: "Object",
      init: {
        progressLabel: qx.locale.Manager.tr("Waiting ..."),
        value: 0
      },
      nullable: false,
      apply: "__applyInputsPulling"
    }
  },

  statics: {
    DISCLAIMER_TIME: 50000,

    createDisclaimerText: function() {
      const disclaimerText = new qx.ui.basic.Atom().set({
        label: qx.locale.Manager.tr("Please wait, this process may take a few minutes ..."),
        padding: [20, 10],
        gap: 15,
        icon: "@FontAwesome5Solid/exclamation-triangle/16",
        backgroundColor: "disclaimer-bg",
        textColor: "info",
        alignX: "center"
      });
      disclaimerText.getChildControl("icon").set({
        textColor: "info"
      });
      return disclaimerText;
    },
  },

  members: {
    __mainLoadingPage: null,
    __overallProgressBar: null,
    __clusterUpScalingLayout: null,
    __pullingSidecarLayout: null,
    __pullingOutputsLayout: null,
    __pullingStateLayout: null,
    __pullingImagesLayout: null,
    __startingSoftwareLayout: null,
    __pullingInputsLayout: null,
    __disclaimerTimer: null,
    __disclaimerText: null,

    getDefaultStartValues: function() {
      return {
        progressLabel: qx.locale.Manager.tr("Waiting ..."),
        value: 0
      }
    },

    getDefaultEndValues: function() {
      return {
        progressLabel: "100%",
        value: 1
      }
    },

    getWidgetForLoadingPage: function() {
      return this.__mainLoadingPage;
    },

    resetSequence: function() {
      if (this.__disclaimerTimer) {
        clearTimeout(this.__disclaimerTimer);
      }
      const defaultVals = this.getDefaultStartValues();
      this.setOverallProgress(0);
      this.setClusterUpScaling(defaultVals);
      this.setSidecarPulling(defaultVals);
      this.setOutputsPulling(defaultVals);
      this.setStatePulling(defaultVals);
      this.setImagesPulling(defaultVals);
      this.setStartingSoftware(defaultVals);
      this.setInputsPulling(defaultVals);
    },

    getProgress: function(report) {
      if (report.unit) {
        const attempt = ("attempt" in report && report["attempt"] > 1) ? `(attempt ${report["attempt"]}) ` : "";
        const currentValue = osparc.utils.Utils.bytesToSize(report["actual_value"], 1, false);
        const totalValue = osparc.utils.Utils.bytesToSize(report["total"], 1, false)
        return {
          progressLabel: `${attempt}${currentValue} / ${totalValue}`,
          value: report["actual_value"] / report["total"]
        }
      }
      const percentage = parseFloat((report["actual_value"] / report["total"] * 100).toFixed(2))
      return {
        progressLabel: `${percentage}%`,
        value: report["actual_value"] / report["total"]
      }
    },

    addProgressMessage: function(progressType, progressReport) {
      const progress = this.getProgress(progressReport);
      switch (progressType) {
        case "CLUSTER_UP_SCALING":
          this.setClusterUpScaling(progress);
          break;
        case "SIDECARS_PULLING":
          this.setSidecarPulling(progress);
          break;
        case "SERVICE_OUTPUTS_PULLING":
          this.setOutputsPulling(progress);
          break;
        case "SERVICE_STATE_PULLING":
          this.setStatePulling(progress);
          break;
        case "SERVICE_IMAGES_PULLING":
          this.setImagesPulling(progress);
          break;
        case "SERVICE_CONTAINERS_STARTING":
          this.setStartingSoftware(progress);
          break;
        case "SERVICE_INPUTS_PULLING":
          this.setInputsPulling(progress);
          break;
      }
    },

    __initLayout: function() {
      this.__mainLoadingPage = new qx.ui.container.Composite(new qx.ui.layout.VBox(8)).set({
        maxWidth: 400,
      });

      const sequenceLoadingPage = new osparc.widget.ProgressSequence(qx.locale.Manager.tr("LOADING ..."));
      const nTasks = 7;
      this.__overallProgressBar = sequenceLoadingPage.addOverallProgressBar(nTasks);
      this.__clusterUpScalingLayout = sequenceLoadingPage.addNewTask(qx.locale.Manager.tr("Provisioning resources ..."));
      this.__pullingSidecarLayout = sequenceLoadingPage.addNewTask(qx.locale.Manager.tr("Setting up system software ..."));
      this.__pullingOutputsLayout = sequenceLoadingPage.addNewTask(qx.locale.Manager.tr("Retrieving your output data ..."));
      this.__pullingStateLayout = sequenceLoadingPage.addNewTask(qx.locale.Manager.tr("Retrieving your work ..."));
      this.__pullingImagesLayout = sequenceLoadingPage.addNewTask(qx.locale.Manager.tr("Installing services ..."));
      this.__startingSoftwareLayout = sequenceLoadingPage.addNewTask(qx.locale.Manager.tr("Starting services ..."));
      this.__pullingInputsLayout = sequenceLoadingPage.addNewTask(qx.locale.Manager.tr("Retrieving your input data ..."));
      this.__mainLoadingPage.addAt(sequenceLoadingPage, 0, {
        flex: 1
      });

      const disclaimerText = this.__disclaimerText = this.self().createDisclaimerText();
      disclaimerText.exclude();
      this.__mainLoadingPage.addAt(this.__disclaimerText, 1, {
        flex: 1
      });
    },

    __computeOverallProgress: function() {
      const overallProgress = this.getClusterUpScaling().value +
      this.getSidecarPulling().value +
      this.getOutputsPulling().value +
      this.getStatePulling().value +
      this.getImagesPulling().value +
      this.getInputsPulling().value;
      this.setOverallProgress(overallProgress)
    },

    __applyOverallProgress: function(value) {
      if (value > 0 && value < 6) {
        this.__disclaimerTimer = setTimeout(() => this.__disclaimerText.show(), this.self().DISCLAIMER_TIME);
      } else {
        this.__disclaimerText.exclude();
      }

      osparc.widget.ProgressSequence.progressUpdate(this.__overallProgressBar, value);
    },

    __applyClusterUpScaling: function(value) {
      osparc.widget.ProgressSequence.updateTaskProgress(this.__clusterUpScalingLayout, value);

      this.__computeOverallProgress();
    },

    __applySidecarPulling: function(value) {
      if (value.value > 0) {
        const defaultEndVals = this.getDefaultEndValues();
        this.setClusterUpScaling(defaultEndVals);
      }
      osparc.widget.ProgressSequence.updateTaskProgress(this.__pullingSidecarLayout, value);

      this.__computeOverallProgress();
    },

    __applyOutputsPulling: function(value) {
      if (value.value > 0) {
        const defaultEndVals = this.getDefaultEndValues();
        this.setSidecarPulling(defaultEndVals);
      }
      osparc.widget.ProgressSequence.updateTaskProgress(this.__pullingOutputsLayout, value);

      this.__computeOverallProgress();
    },

    __applyStatePulling: function(value) {
      if (value.value > 0) {
        const defaultEndVals = this.getDefaultEndValues();
        this.setSidecarPulling(defaultEndVals);
      }
      osparc.widget.ProgressSequence.updateTaskProgress(this.__pullingStateLayout, value);

      this.__computeOverallProgress();
    },

    __applyImagesPulling: function(value) {
      if (value.value > 0) {
        const defaultEndVals = this.getDefaultEndValues();
        this.setSidecarPulling(defaultEndVals);
      }
      osparc.widget.ProgressSequence.updateTaskProgress(this.__pullingImagesLayout, value);

      this.__computeOverallProgress();
    },

    __applyStartingSoftware: function(value) {
      if (value.value > 0) {
        const defaultEndVals = this.getDefaultEndValues();
        this.setSidecarPulling(defaultEndVals);
      }
      osparc.widget.ProgressSequence.updateTaskProgress(this.__startingSoftwareLayout, value);

      this.__computeOverallProgress();
    },

    __applyInputsPulling: function(value) {
      if (value.value > 0) {
        const defaultEndVals = this.getDefaultEndValues();
        this.setSidecarPulling(defaultEndVals);
      }
      osparc.widget.ProgressSequence.updateTaskProgress(this.__pullingInputsLayout, value);

      this.__computeOverallProgress();
    }
  }
});
