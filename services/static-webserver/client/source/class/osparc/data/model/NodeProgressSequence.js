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
      check: "Number",
      init: 0,
      nullable: false,
      apply: "__applyClusterUpScaling"
    },

    sidecarPulling: {
      check: "Number",
      init: 0,
      nullable: false,
      apply: "__applySidecarPulling"
    },

    outputsPulling: {
      check: "Number",
      init: 0,
      nullable: false,
      apply: "__applyOutputsPulling"
    },

    statePulling: {
      check: "Number",
      init: 0,
      nullable: false,
      apply: "__applyStatePulling"
    },

    imagesPulling: {
      check: "Number",
      init: 0,
      nullable: false,
      apply: "__applyImagesPulling"
    },

    inputsPulling: {
      check: "Number",
      init: 0,
      nullable: false,
      apply: "__applyInputsPulling"
    }
  },

  statics: {
    NODE_INDEX: {
      LABEL: 0,
      HALO: 1,
    },

    createTaskLayout: function(label) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      })).set({
        padding: [2, 10]
      });

      const lbl = new qx.ui.basic.Label(label);
      lbl.set({
        textColor: "text",
        allowGrowX: true,
        allowShrinkX: true,
      });
      layout.addAt(lbl, this.NODE_INDEX.LABEL, {
        flex: 1
      });

      const iconContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
        alignY: "middle",
        alignX: "center",
      })).set({
        height: 18,
        width: 18,
        allowGrowY: false,
        allowGrowX: false,
      });
      const icon = new qx.ui.basic.Image("@FontAwesome5Solid/check/10").set({
        visibility: "excluded",
        textColor: "success"
      });
      iconContainer.add(icon);
      const progressColor = qx.theme.manager.Color.getInstance().resolve("progressbar");
      osparc.service.StatusUI.getStatusHalo(iconContainer, progressColor, 0);
      layout.addAt(iconContainer, this.NODE_INDEX.HALO);

      return layout;
    },

    createProgressBar: function(max = 1) {
      const progressBar = new qx.ui.indicator.ProgressBar().set({
        maximum: max,
        height: 4,
        margin: 0,
        padding: 0
      });
      progressBar.exclude();
      return progressBar;
    },

    updateProgressLabel: function(atom, value) {
      if ([null, undefined].includes(value)) {
        return;
      }

      if (atom) {
        const halo = atom.getChildren()[this.NODE_INDEX.HALO];
        const icon = halo.getChildren()[0];
        icon.setVisibility(value === 1 ? "visible" : "excluded");
        const progressColor = qx.theme.manager.Color.getInstance().resolve("progressbar")
        osparc.service.StatusUI.getStatusHalo(halo, progressColor, value * 100);
      }
    },

    progressReceived: function(pBar, value) {
      if ([null, undefined].includes(value)) {
        return;
      }

      if (pBar) {
        pBar.set({
          value,
          visibility: (value >= 0) ? "visible" : "excluded"
        });
      }
    }
  },

  members: {
    __mainLoadingPage: null,
    __overallProgressBar: null,
    __clusterUpScalingLayout: null,
    __pullingSidecarLayout: null,
    __pullingOutputsLayout: null,
    __pullingStateLayout: null,
    __pullingImagesLayout: null,
    __pullingInputsLayout: null,
    __disclaimerText: null,

    getWidgetForLoadingPage: function() {
      return this.__mainLoadingPage;
    },

    resetSequence: function() {
      this.setOverallProgress(0);
      this.setClusterUpScaling(0);
      this.setSidecarPulling(0);
      this.setOutputsPulling(0);
      this.setStatePulling(0);
      this.setImagesPulling(0);
      this.setInputsPulling(0);
    },

    addProgressMessage: function(progressType, progress) {
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
        case "SERVICE_INPUTS_PULLING":
          this.setInputsPulling(progress);
          break;
      }
    },

    __initLayout: function() {
      this.__mainLoadingPage = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));


      const sequenceLoadingPage = new qx.ui.container.Composite(new qx.ui.layout.VBox(9)).set({
        backgroundColor: "window-popup-background",
        paddingBottom: 8
      });

      const progressTitle = new qx.ui.basic.Label(qx.locale.Manager.tr("LOADING...")).set({
        font: "text-12",
        alignX: "center",
        alignY: "middle",
        margin: 10
      });
      const nTasks = 6;
      const overallPBar = this.__overallProgressBar = this.self().createProgressBar(nTasks);
      sequenceLoadingPage.add(progressTitle);
      sequenceLoadingPage.add(overallPBar);

      const disclaimerText = this.__disclaimerText = new qx.ui.basic.Atom().set({
        label: qx.locale.Manager.tr("Please be patient, this process can take a few minutes..."),
        padding: [20, 10],
        gap: 15,
        icon: "@FontAwesome5Solid/exclamation-triangle/16",
        backgroundColor: "disclaimer-bg",
        textColor: "info",
        alignX: "center"
      });
      const icon = disclaimerText.getChildControl("icon");
      icon.set({
        textColor: "info"
      })
      disclaimerText.exclude();


      const scalingLayout = this.__clusterUpScalingLayout = this.self().createTaskLayout(qx.locale.Manager.tr("Increasing system capacity..."));
      sequenceLoadingPage.add(scalingLayout);

      const pullingInputsLayout = this.__pullingInputsLayout = this.self().createTaskLayout(qx.locale.Manager.tr("Retrieving your input data..."));
      sequenceLoadingPage.add(pullingInputsLayout);

      const pullingSidecarLayout = this.__pullingSidecarLayout = this.self().createTaskLayout(qx.locale.Manager.tr("Setting up key components..."));
      sequenceLoadingPage.add(pullingSidecarLayout);

      const pullingOutputsLayout = this.__pullingOutputsLayout = this.self().createTaskLayout(qx.locale.Manager.tr("Retrieving your output data..."));
      sequenceLoadingPage.add(pullingOutputsLayout);

      const pullingStateLayout = this.__pullingStateLayout = this.self().createTaskLayout(qx.locale.Manager.tr("Retrieving your work..."));
      sequenceLoadingPage.add(pullingStateLayout);

      const pullingImagesLayout = this.__pullingImagesLayout = this.self().createTaskLayout(qx.locale.Manager.tr("Installing software..."));
      sequenceLoadingPage.add(pullingImagesLayout);

      this.__mainLoadingPage.addAt(sequenceLoadingPage, 0, {
        flex: 1
      });
      this.__mainLoadingPage.addAt(this.__disclaimerText, 1, {
        flex: 1
      });
    },

    __computeOverallProgress: function() {
      const overallProgress = this.getClusterUpScaling() +
      this.getSidecarPulling() +
      this.getOutputsPulling() +
      this.getStatePulling() +
      this.getImagesPulling() +
      this.getInputsPulling();
      this.setOverallProgress(overallProgress)
    },

    __applyOverallProgress: function(value) {
      if (value > 0 && value < 6) {
        setTimeout(() => {
          this.__disclaimerText.show();
        }, 50000);
      } else {
        this.__disclaimerText.exclude();
      }

      this.self().progressReceived(this.__overallProgressBar, value);
    },

    __applyClusterUpScaling: function(value) {
      this.self().updateProgressLabel(this.__clusterUpScalingLayout, value);

      this.__computeOverallProgress();
    },

    __applySidecarPulling: function(value) {
      if (value > 0) {
        this.setClusterUpScaling(1);
      }
      this.self().updateProgressLabel(this.__pullingSidecarLayout, value);

      this.__computeOverallProgress();
    },

    __applyOutputsPulling: function(value) {
      if (value > 0) {
        this.setSidecarPulling(1);
      }
      this.self().updateProgressLabel(this.__pullingOutputsLayout, value);

      this.__computeOverallProgress();
    },

    __applyStatePulling: function(value) {
      if (value > 0) {
        this.setSidecarPulling(1);
      }
      this.self().updateProgressLabel(this.__pullingStateLayout, value);

      this.__computeOverallProgress();
    },

    __applyImagesPulling: function(value) {
      if (value > 0) {
        this.setSidecarPulling(1);
      }
      this.self().updateProgressLabel(this.__pullingImagesLayout, value);

      this.__computeOverallProgress();
    },

    __applyInputsPulling: function(value) {
      if (value > 0) {
        this.setSidecarPulling(1);
      }
      this.self().updateProgressLabel(this.__pullingInputsLayout, value);

      this.__computeOverallProgress();
    }
  }
});
