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

    showPricingUnits: async function(nodeIds) {
      const unitsLoading = () => this.fireEvent("loadingUnits");
      const unitsAdded = () => this.fireEvent("unitsReady");
      unitsLoading();
      this._removeAll();
      const advancedCB = new qx.ui.form.CheckBox().set({
        label: this.tr("More information"),
        value: false
      });
      if ("workbench" in this.__studyData) {
        const workbench = this.__studyData["workbench"];
        Object.keys(workbench).forEach(nodeId => {
          const node = workbench[nodeId];
          if (nodeIds && !nodeIds.includes(nodeId)) {
            return;
          }
          const plansParams = {
            url: osparc.data.Resources.getServiceUrl(
              node["key"],
              node["version"]
            )
          };
          osparc.data.Resources.fetch("services", "pricingPlans", plansParams)
            .then(pricingPlans => {
              if (pricingPlans) {
                const unitParams = {
                  url: {
                    studyId: this.__studyData["uuid"],
                    nodeId
                  }
                };
                osparc.data.Resources.fetch("studies", "getPricingUnit", unitParams)
                  .then(preselectedPricingUnit => {
                    const serviceGroup = this.__createPricingUnitsGroup(node["label"], pricingPlans, preselectedPricingUnit, advancedCB);
                    if (serviceGroup) {
                      this._addAt(advancedCB, 0);
                      this._add(serviceGroup.layout);

                      const unitButtons = serviceGroup.unitButtons;
                      unitButtons.addListener("changeSelectedUnit", e => {
                        unitButtons.setEnabled(false);
                        const selectedPricingUnit = e.getData();
                        this.__pricingUnitSelected(nodeId, pricingPlans["pricingPlanId"], selectedPricingUnit)
                          .finally(() => unitButtons.setEnabled(true));
                      });

                      unitsAdded();
                    }
                  });
              }
            });
        });
      }
    },

    __createPricingUnitsGroup: function(nodeLabel, pricingPlans, preselectedPricingUnit, advancedCB) {
      if (pricingPlans && "pricingUnits" in pricingPlans && pricingPlans["pricingUnits"].length) {
        const pricingUnitsLayout = osparc.study.StudyOptions.createGroupBox(nodeLabel);

        const unitButtons = new osparc.study.PricingUnits(pricingPlans["pricingUnits"], preselectedPricingUnit);
        advancedCB.bind("value", unitButtons, "advanced");
        pricingUnitsLayout.add(unitButtons);

        return {
          layout: pricingUnitsLayout,
          unitButtons
        };
      }
      return null;
    },

    __pricingUnitSelected: function(nodeId, pricingPlanId, selectedPricingUnit) {
      const params = {
        url: {
          studyId: this.__studyData["uuid"],
          nodeId,
          pricingPlanId,
          pricingUnitId: selectedPricingUnit["pricingUnitId"]
        }
      };
      return osparc.data.Resources.fetch("studies", "putPricingUnit", params);
    }
  }
});
