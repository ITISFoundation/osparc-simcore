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

    this.__sequenceLoadingPage = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
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

  members: {
    __sequenceLoadingPage: null,

    getSequenceForLoadingPage: function() {
      const label = new qx.ui.basic.Label("Hey there");
      return label;
    },

    addProgressMessage: function(progressType, progress) {
      console.log(progressType, progress);
    },

    __applyClusterUp: function(value) {

    },

    __applySidecarPulling: function(value) {
      this.setClusterUpScaling(1);
    },

    __applyInputsPulling: function(value) {
      this.setSidecarPulling(1);
    },

    __applyOutputsPulling: function(value) {
      this.setSidecarPulling(1);
    },

    __applyStatePulling: function(value) {
      this.setSidecarPulling(1);
    },

    __applyImagesPulling: function(value) {
      this.setInputsPulling(1);
      this.setOutputsPulling(1);
      this.setStatePulling(1);
    }
  }
});
