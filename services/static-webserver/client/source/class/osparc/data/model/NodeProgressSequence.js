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
    NODE_INDEX: {
      LABEL: 0,
      HALO: 1,
    },
    createTitleAtom: function(label) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      const lbl = this.__label = new qx.ui.basic.Label(label);
      lbl.set({
        textColor: "text",
        allowGrowX: true,
        allowShrinkX: true,
      });
      layout.addAt(lbl, this.NODE_INDEX.LABEL, {
        flex: 1
      });

      const iconContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignY: "middle",
        alignX: "center",
      })).set({
        height: 18,
        width: 18,
        allowGrowY: false,
        allowGrowX: false,
      });
      const icon = this.__ICON = new qx.ui.basic.Image(
        "@FontAwesome5Solid/check/14"
      ).set({
        visibility: "excluded"
      });
      iconContainer.add(icon);
      const progressColor = qx.theme.manager.Color.getInstance().resolve("progressbar");
      osparc.service.StatusUI.getStatusHalo(iconContainer, progressColor, 0);
      layout.addAt(iconContainer, this.NODE_INDEX.HALO);
      layout.set({
        padding: [2, 10]
      })
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
        if (value === 1) {
          icon.set({
            visibility: "visible"
          });
        } else {
          icon.set({
            visibility: "excluded"
          });
        }
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
      if (value === 1) {
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
      if (this.getSidecarPulling() < 1) {
        this.setSidecarPulling(1);
        const progress = this.getDefaultProgress();
        this.setDefaultProgress(progress + 1);
      }
      this.self().updateProgressLabel(this.__pullingImagesTitle, value);
    },

    __applyInputsPulling: function(value) {
      if (this.getSidecarPulling() < 1) {
        this.setSidecarPulling(1);
        const progress = this.getDefaultProgress();
        this.setDefaultProgress(progress + 1);
      }
      this.self().updateProgressLabel(this.__pullingInputsTitle, value);
    }
  }
});
