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

  members: {
    __sequenceLoadingPage: null,

    addProgressMessage: function(progressType, progress) {
      console.log(progressType, progress);
    },

    getSequenceForLoadingPage: function() {
      const label = new qx.ui.basic.Label("Hey there");
      return label;
    }
  }
});
