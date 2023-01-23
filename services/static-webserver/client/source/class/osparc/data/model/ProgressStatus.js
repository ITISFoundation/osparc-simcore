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
 * - CLUSTER_UP_SCALING
 * - SIDECAR_PULLING
 * - SERVICE_INPUTS_PULLING
 * - SERVICE_OUTPUTS_PULLING
 * - SERVICE_STATE_PULLING
 * - SERVICE_IMAGES_PULLING
 *
 * This class provides different widgets that render the progress status
 *
 */


qx.Class.define("osparc.data.model.ProgressStatus", {
  extend: qx.core.Object,

  construct: function() {
    this.base(arguments);

    this.__initLayout();
  },

  properties: {
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

    inputsPulling: {
      check: "Number",
      init: 0,
      nullable: false,
      apply: "__applyInputsPulling"
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
    }
  },

  statics: {
    createTitleAtom: function(label) {
      const atom = new qx.ui.basic.Atom().set({
        label,
        font: "text-14",
        icon: "@FontAwesome5Solid/circle-notch/16",
        gap: 15
      });
      const icon = atom.getChildControl("icon");
      osparc.utils.StatusUI.updateIconAnimation(icon);
      return atom;
    },

    createProgressBar: function() {
      const progressBar = new qx.ui.indicator.ProgressBar().set({
        height: 10
      });
      progressBar.getChildControl("progress").set({
        backgroundColor: "strong-main"
      });
      progressBar.exclude();
      return progressBar;
    },

    progressReceived: function(atom, pBar, value) {
      if (![null, undefined].includes(value)) {
        return;
      }

      if (atom) {
        if (value === 1) {
          atom.setIcon("@FontAwesome5Solid/check/16");
        } else {
          atom.setIcon("@FontAwesome5Solid/circle-notch/16");
        }
        const icon = atom.getChildControl("icon");
        osparc.utils.StatusUI.updateIconAnimation(icon);
      }

      if (pBar) {
        pBar.set({
          value,
          visibility: (value > 0 && value < 1) ? "visible" : "excluded"
        });
      }
    }
  },

  members: {
    __sequenceLoadingPage: null,
    __clusterUpScalingTitle: null,
    __clusterUpScalingSubtitle: null,
    __pullingSidecarTitle: null,
    __pullingSidecarPBar: null,
    __pullingInputsTitle: null,
    __pullingInputsPBar: null,
    __pullingOutputsTitle: null,
    __pullingOutputsPBar: null,
    __pullingStateTitle: null,
    __pullingStatePBar: null,
    __pullingImagesTitle: null,
    __pullingImagesPBar: null,

    getSequenceForLoadingPage: function() {
      return this.__sequenceLoadingPage;
    },

    addProgressMessage: function(progressType, progress) {
      console.log(progressType, progress);

      switch (progressType) {
        case "CLUSTER_UP_SCALING":
          this.setClusterUpScaling(progress);
          break;
        case "SIDECAR_PULLING":
          this.setSidecarPulling(progress);
          break;
        case "SERVICE_INPUTS_PULLING":
          this.setInputsPulling(progress);
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
      }
    },

    __initLayout: function() {
      this.__sequenceLoadingPage = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const scalingTitle = this.__clusterUpScalingTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Scaling up the cluster..."));
      this.__sequenceLoadingPage.add(scalingTitle);

      const scalingSubtitle = this.__clusterUpScalingSubtitle = new qx.ui.basic.Label(qx.locale.Manager.tr("This step can take up to 3 minutes"));
      scalingSubtitle.exclude();
      this.__sequenceLoadingPage.add(scalingSubtitle);

      const pullingSidecarTitle = this.__pullingSidecarTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Pulling sidecar..."));
      this.__sequenceLoadingPage.add(pullingSidecarTitle);

      const pullingSidecarPBar = this.__pullingSidecarPBar = this.self().createProgressBar();
      this.__sequenceLoadingPage.add(pullingSidecarPBar);

      const pullingInputsTitle = this.__pullingInputsTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Pulling inputs..."));
      this.__sequenceLoadingPage.add(pullingInputsTitle);

      const pullingInputsPBar = this.__pullingInputsPBar = this.self().createProgressBar();
      this.__sequenceLoadingPage.add(pullingInputsPBar);

      const pullingOutputsTitle = this.__pullingOutputsTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Pulling outputs..."));
      this.__sequenceLoadingPage.add(pullingOutputsTitle);

      const pullingOutputsPBar = this.__pullingOutputsPBar = this.self().createProgressBar();
      this.__sequenceLoadingPage.add(pullingOutputsPBar);

      const pullingStateTitle = this.__pullingStateTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Pulling state..."));
      this.__sequenceLoadingPage.add(pullingStateTitle);

      const pullingStatePBar = this.__pullingStatePBar = this.self().createProgressBar();
      this.__sequenceLoadingPage.add(pullingStatePBar);

      const pullingImagesTitle = this.__pullingImagesTitle = this.self().createTitleAtom(qx.locale.Manager.tr("Pulling images..."));
      this.__sequenceLoadingPage.add(pullingImagesTitle);

      const pullingImagesPBar = this.__pullingImagesPBar = this.self().createProgressBar();
      this.__sequenceLoadingPage.add(pullingImagesPBar);
    },

    __applyClusterUpScaling: function(value) {
      this.self().progressReceived(this.__clusterUpScalingTitle, null, value);

      if (value > 0 && value < 1) {
        this.__clusterUpScalingSubtitle.show();
      } else {
        this.__clusterUpScalingSubtitle.exclude();
      }
    },

    __applySidecarPulling: function(value) {
      this.setClusterUpScaling(1);

      this.self().progressReceived(this.__pullingSidecarTitle, this.__pullingSidecarPBar, value);
    },

    __applyInputsPulling: function(value) {
      this.setSidecarPulling(1);

      this.self().progressReceived(this.__pullingInputsTitle, this.__pullingInputsPBar, value);
    },

    __applyOutputsPulling: function(value) {
      this.setSidecarPulling(1);

      this.self().progressReceived(this.__pullingOutputsTitle, this.__pullingOutputsPBar, value);
    },

    __applyStatePulling: function(value) {
      this.setSidecarPulling(1);

      this.self().progressReceived(this.__pullingStateTitle, this.__pullingStatePBar, value);
    },

    __applyImagesPulling: function(value) {
      this.setInputsPulling(1);
      this.setOutputsPulling(1);
      this.setStatePulling(1);

      this.self().progressReceived(this.__pullingImagesTitle, this.__pullingImagesPBar, value);
    }
  }
});
