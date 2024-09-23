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

qx.Class.define("osparc.study.StudyPricingUnits", {
  extend: qx.ui.container.Composite,

  construct: function(studyData) {
    this.base(arguments);

    this.set({
      layout: new qx.ui.layout.VBox(5)
    });

    this.__studyData = studyData;

    this.__showPricingUnits();
  },

  events: {
    "loadingUnits": "qx.event.type.Event",
    "unitsReady": "qx.event.type.Event"
  },

  members: {
    __studyData: null,

    __showPricingUnits: function() {
      const unitsLoading = () => this.fireEvent("loadingUnits");
      const unitsAdded = () => this.fireEvent("unitsReady");
      unitsLoading();
      this._removeAll();
      const promises = [];
      if ("workbench" in this.__studyData) {
        const workbench = this.__studyData["workbench"];
        Object.keys(workbench).forEach(nodeId => {
          const node = workbench[nodeId];
          if (osparc.data.model.Node.isFrontend(node)) {
            return;
          }
          const nodePricingUnits = new osparc.study.NodePricingUnits(this.__studyData["uuid"], nodeId, node);
          this._add(nodePricingUnits);
          promises.push(nodePricingUnits.showPricingUnits());
        });
      }
      Promise.all(promises)
        .then(() => unitsAdded());
    }
  }
});
