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

    this.__nodePricingUnits = [];

    if (studyData) {
      this.setStudyData(studyData);
    }
  },

  events: {
    "loadingUnits": "qx.event.type.Event",
    "unitsReady": "qx.event.type.Event"
  },

  statics: {
    includeInList: function(node) {
      return !osparc.data.model.Node.isFrontend(node);
    },
  },

  members: {
    __studyData: null,
    __nodePricingUnits: null,

    setStudyData: function(studyData) {
      this.__studyData = studyData;
      this.__showPricingUnits();
    },

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
          if (this.self().includeInList(node)) {
            const nodePricingUnits = new osparc.study.NodePricingUnits(this.__studyData["uuid"], nodeId, node);
            this.__nodePricingUnits.push(nodePricingUnits);
            this._add(nodePricingUnits);
            promises.push(nodePricingUnits.showPricingUnits());
          }
        });
      }
      Promise.all(promises)
        .then(() => unitsAdded());
    },

    getNodePricingUnits: function() {
      return this.__nodePricingUnits;
    },
  }
});
