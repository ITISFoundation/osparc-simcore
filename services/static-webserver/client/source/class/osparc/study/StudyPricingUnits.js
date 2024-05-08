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

    this.showPricingUnits();
  },

  events: {
    "loadingUnits": "qx.event.type.Event",
    "unitsReady": "qx.event.type.Event"
  },

  members: {
    __studyData: null,

    showPricingUnits: function() {
      const unitsLoading = () => this.fireEvent("loadingUnits");
      const unitsAdded = () => this.fireEvent("unitsReady");
      unitsLoading();
      this._removeAll();
      const promises = [];
      if ("workbench" in this.__studyData) {
        const workbench = this.__studyData["workbench"];
        Object.keys(workbench).forEach(nodeId => {
          const node = workbench[nodeId];
          const nodePricingUnits = new osparc.study.NodePricingUnits(this.__studyData["uuid"], nodeId, node);
          this._add(nodePricingUnits);
          promises.push(nodePricingUnits.showPricingUnits());
        });
      }
      Promise.all(promises)
        .then(() => unitsAdded());
    },

    __createPricingUnitsGroup: function(nodeLabel, pricingPlans, preselectedPricingUnit) {
      if (pricingPlans && "pricingUnits" in pricingPlans && pricingPlans["pricingUnits"].length) {
        const pricingUnitsLayout = osparc.study.StudyOptions.createGroupBox(nodeLabel);

        const unitButtons = new osparc.study.PricingUnits(pricingPlans["pricingUnits"], preselectedPricingUnit);
        pricingUnitsLayout.add(unitButtons);

        return {
          layout: pricingUnitsLayout,
          unitButtons
        };
      }
      return null;
    },

    __pricingUnitSelected: function(nodeId, pricingPlanId, selectedPricingUnitId) {
      const params = {
        url: {
          studyId: this.__studyData["uuid"],
          nodeId,
          pricingPlanId,
          pricingUnitId: selectedPricingUnitId
        }
      };
      return osparc.data.Resources.fetch("studies", "putPricingUnit", params);
    }
  }
});
