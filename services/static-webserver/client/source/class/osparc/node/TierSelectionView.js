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

qx.Class.define("osparc.node.TierSelectionView", {
  extend: osparc.node.ServiceOptionsView,

  events: {
    "tierChanged": "qx.event.type.Event"
  },

  members: {
    _applyNode: function(node) {
      this.__populateLayout();

      this.base(arguments, node);
    },

    __populateLayout: function() {
      this._removeAll();

      this._add(new qx.ui.basic.Label(this.tr("Tier Options")).set({
        font: "text-14"
      }));

      const instructionsMsg = this.tr("Please Stop the Service and then change the Tier");
      const instructionsLabel = new qx.ui.basic.Label(instructionsMsg).set({
        rich: true
      });
      this._add(instructionsLabel);

      const node = this.getNode();

      const nodePricingUnits = new osparc.study.NodePricingUnits(node.getStudy().getUuid(), node.getNodeId(), node);
      nodePricingUnits.showPricingUnits(false);
      this._add(nodePricingUnits);
    }
  }
});
