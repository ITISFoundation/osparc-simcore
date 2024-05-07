/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.study.NodePricingUnits", {
  extend: qx.ui.container.Composite,

  construct: function(nodeData, studyId, nodeId) {
    this.base(arguments);

    this.set({
      layout: new qx.ui.layout.VBox(5)
    });

    this.__nodeData = nodeData;
    this.__studyId = studyId;
    this.__nodeId = nodeId;
  },

  members: {
    __nodeData: null,
    __studyId: null,
    __nodeId: null,

    showPricingUnits: function() {
      return new Promise(resolve => {
        const nodeKey = this.__nodeData["key"];
        const nodeVersion = this.__nodeData["version"];
        const nodeLabel = this.__nodeData["label"];
        const studyId = this.__studyId;
        const nodeId = this.__nodeId;

        const plansParams = {
          url: osparc.data.Resources.getServiceUrl(
            nodeKey,
            nodeVersion
          )
        };
        osparc.data.Resources.fetch("services", "pricingPlans", plansParams)
          .then(pricingPlans => {
            if (pricingPlans) {
              const unitParams = {
                url: {
                  studyId,
                  nodeId
                }
              };
              osparc.data.Resources.fetch("studies", "getPricingUnit", unitParams)
                .then(preselectedPricingUnit => {
                  const serviceGroup = this.__createPricingUnitsGroup(nodeLabel, pricingPlans, preselectedPricingUnit);
                  if (serviceGroup) {
                    this._add(serviceGroup.layout);

                    const unitButtons = serviceGroup.unitButtons;
                    unitButtons.addListener("changeSelectedUnitId", e => {
                      unitButtons.setEnabled(false);
                      const selectedPricingUnitId = e.getData();
                      this.__pricingUnitSelected(nodeId, pricingPlans["pricingPlanId"], selectedPricingUnitId)
                        .finally(() => unitButtons.setEnabled(true));
                    });
                  }
                })
                .finally(() => resolve());
            }
          });
      });
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
          studyId: this.__studyId,
          nodeId,
          pricingPlanId,
          pricingUnitId: selectedPricingUnitId
        }
      };
      return osparc.data.Resources.fetch("studies", "putPricingUnit", params);
    }
  }
});
