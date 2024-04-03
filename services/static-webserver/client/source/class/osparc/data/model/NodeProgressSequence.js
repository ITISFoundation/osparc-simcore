/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * The progress sequence of a dynamic service is as follows:
 *
 * [CLUSTER_UP_SCALING]
 * [SIDECARS_PULLING]
 * [SERVICE_OUTPUTS_PULLING, SERVICE_STATE_PULLING] (notice the parallelism here)
 * [SERVICE_IMAGES_PULLING]
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
    defaultProgress: {
      check: "Number",
      init: null,
      nullable: false,
      apply: "__applyDefaultProgress"
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
      init: null,
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
    createTitleAtom: function(label) {
      const atom = new qx.ui.basic.Atom().set({
        label,
        iconPosition: "right",
        font: "text-14",
        icon: "@FontAwesome5Solid/circle-notch/14",
        gap: 15,
        margin: [5, 10]
      });
      const lbl = atom.getChildControl("label");
      lbl.set({
        allowGrowX: true,
        allowShrinkX: true
      })
      const icon = atom.getChildControl("icon");
      icon.set({
        allowGrowX: false,
        allowShrinkX: false
      })
      osparc.service.StatusUI.updateCircleAnimation(icon);
      return atom;
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
        if (value === 1) {
          atom.setIcon("@FontAwesome5Solid/check/14");
        } else {
          atom.setIcon("@FontAwesome5Solid/circle-notch/14");
        }
        const icon = atom.getChildControl("icon");
        osparc.service.StatusUI.updateCircleAnimation(icon);
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
    __sequenceLoadingPage: null,
    __defaultProgressBar: null,
    __clusterUpScalingTitle: null,
    __pullingSidecarTitle: null,
    __pullingOutputsTitle: null,
    __pullingStateTitle: null,
    __pullingImagesTitle: null,
    __pullingInputsTitle: null,
    __disclaimerText: null,

    getWidgetForLoadingPage: function() {
      return this.__mainLoadingPage;
    },

    resetSequence: function() {
      this.setDefaultProgress(0);
      this.setClusterUpScaling(0);
      this.setSidecarPulling(0);
      this.setOutputsPulling(0);
      this.setStatePulling(0);
      this.setImagesPulling(0);
      this.setInputsPulling(0);
    },

    addProgressMessage: function(progressType, progress) {
      const defaultProgress = this.getClusterUpScaling() +
        this.getSidecarPulling() +
        this.getOutputsPulling() +
        this.getStatePulling() +
        this.getImagesPulling() +
        this.getInputsPulling();
      if (progress) {
        const val = defaultProgress
        this.setDefaultProgress(val)
      }

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
        backgroundColor: "window-popup-background"
      });

      const progressTitle = new qx.ui.basic.Label(qx.locale.Manager.tr("LOADING...")).set({
        font: "text-12",
        alignX: "center",
        alignY: "middle",
        margin: 10
      });
      const defaultPBar = this.__defaultProgressBar = this.self().createProgressBar(6);
      sequenceLoadingPage.add(progressTitle);
      sequenceLoadingPage.add(defaultPBar);

      const defaultProgressSubtitle = this.__disclaimerText = new qx.ui.basic.Atom().set({
        label: qx.locale.Manager.tr("Please be patient, this process can take a few minutes..."),
        padding: [20, 10],
        gap: 15,
        icon: "@FontAwesome5Solid/exclamation-triangle/16",
        backgroundColor: "disclaimer-bg",
        textColor: "info",
        alignX: "center"
      });
      const icon = defaultProgressSubtitle.getChildControl("icon");
      icon.set({
        textColor: "info"
      })
      defaultProgressSubtitle.exclude();


      const scalingTitle = this.__clusterUpScalingTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Increasing system capacity..."));
      sequenceLoadingPage.add(scalingTitle);

      const pullingInputsTitle = this.__pullingInputsTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Retrieving your input data..."));
      sequenceLoadingPage.add(pullingInputsTitle);

      const pullingSidecarTitle = this.__pullingSidecarTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Setting up key components..."));
      sequenceLoadingPage.add(pullingSidecarTitle);

      const pullingOutputsTitle = this.__pullingOutputsTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Retrieving your output data..."));
      sequenceLoadingPage.add(pullingOutputsTitle);

      const pullingStateTitle = this.__pullingStateTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Retrieving your work..."));
      sequenceLoadingPage.add(pullingStateTitle);

      const pullingImagesTitle = this.__pullingImagesTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Installing software..."));
      sequenceLoadingPage.add(pullingImagesTitle);

      this.__mainLoadingPage.addAt(sequenceLoadingPage, 0, {
        flex: 1
      });
      this.__mainLoadingPage.addAt(this.__disclaimerText, 1, {
        flex: 1
      });
    },

    __applyDefaultProgress: function(value) {
      if (value > 0 && value < 6) {
        setTimeout(() => {
          this.__disclaimerText.show();
        }, 50000);
      } else {
        this.__disclaimerText.exclude();
      }

      this.self().progressReceived(this.__defaultProgressBar, value);
    },

    __applyClusterUpScaling: function(value) {
      this.self().updateProgressLabel(this.__clusterUpScalingTitle, value);
    },

    __applySidecarPulling: function(value) {
      if (this.getClusterUpScaling() < 1) {
        this.setClusterUpScaling(1);
        const progress = this.getDefaultProgress();
        this.setDefaultProgress(progress + 1);
      }
      this.self().updateProgressLabel(this.__pullingSidecarTitle, value);
    },

    __applyOutputsPulling: function(value) {
      if (this.getSidecarPulling() < 1) {
        this.setSidecarPulling(1);
        const progress = this.getDefaultProgress();
        this.setDefaultProgress(progress + 1);
      }
      this.self().updateProgressLabel(this.__pullingOutputsTitle, value);
    },

    __applyStatePulling: function(value) {
      if (this.getSidecarPulling() < 1) {
        this.setSidecarPulling(1);
        const progress = this.getDefaultProgress();
        this.setDefaultProgress(progress + 1);
      }
      this.self().updateProgressLabel(this.__pullingStateTitle, value);
    },

    __applyImagesPulling: function(value) {
      // [SERVICE_OUTPUTS_PULLING, SERVICE_STATE_PULLING] (notice the parallelism here)
      // As the two previous are running in parallel we can assume if this runs both should be done when we start pulling the images
      if (this.getOutputsPulling() < 1) {
        this.setOutputsPulling(1);
        const progress = this.getDefaultProgress();
        this.setDefaultProgress(progress + 1);
      }
      if (this.getStatePulling() < 1) {
        this.setStatePulling(1);
        const progress = this.getDefaultProgress();
        this.setDefaultProgress(progress + 1);
      }
      this.self().updateProgressLabel(this.__pullingImagesTitle, value);
    },

    __applyInputsPulling: function(value) {
      if (this.getImagesPulling() < 1) {
        this.setImagesPulling(1);
        const progress = this.getDefaultProgress();
        this.setDefaultProgress(progress + 1);
      }
      this.self().updateProgressLabel(this.__pullingInputsTitle, value);
    }
  }
});
