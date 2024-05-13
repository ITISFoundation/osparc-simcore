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

  /**
    * @param studyId {String}
    * @param nodeId {String}
    * @param node {osparc.data.model.Node || Object}
    */
  construct: function(studyId, nodeId, node) {
    this.base(arguments);

    this.set({
      layout: new qx.ui.layout.VBox()
    });

    this.__studyId = studyId;
    this.__nodeId = nodeId;
    if (node instanceof osparc.data.model.Node) {
      this.__nodeKey = node.getKey();
      this.__nodeVersion = node.getVersion();
      this.__nodeLabel = node.getLabel();
    } else {
      this.__nodeKey = node["key"];
      this.__nodeVersion = node["version"];
      this.__nodeLabel = node["label"];
    }
  },

  statics: {
    pricingUnitSelected: function(studyId, nodeId, planId, selectedUnitId) {
      const params = {
        url: {
          studyId,
          nodeId,
          pricingPlanId: planId,
          pricingUnitId: selectedUnitId
        }
      };
      return osparc.data.Resources.fetch("studies", "putPricingUnit", params);
    }
  },

  members: {
    __studyId: null,
    __nodeId: null,
    __nodeKey: null,
    __nodeVersion: null,
    __nodeLabel: null,

    showPricingUnits: function(inGroupBox = true) {
      return new Promise(resolve => {
        const nodeKey = this.__nodeKey;
        const nodeVersion = this.__nodeVersion;
        const nodeLabel = this.__nodeLabel;
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
                  if (pricingPlans && "pricingUnits" in pricingPlans && pricingPlans["pricingUnits"].length) {
                    const unitButtons = new osparc.study.PricingUnits(pricingPlans["pricingUnits"], preselectedPricingUnit);
                    if (inGroupBox) {
                      const pricingUnitsLayout = osparc.study.StudyOptions.createGroupBox(nodeLabel);
                      pricingUnitsLayout.add(unitButtons);
                      this._add(pricingUnitsLayout);
                    } else {
                      this._add(unitButtons);
                    }
                    unitButtons.addListener("changeSelectedUnitId", e => {
                      unitButtons.setEnabled(false);
                      const selectedPricingUnitId = e.getData();
                      this.self().pricingUnitSelected(this.__studyId, this.__nodeId, pricingPlans["pricingPlanId"], selectedPricingUnitId)
                        .finally(() => unitButtons.setEnabled(true));
                    });
                  }
                })
                .finally(() => resolve());
            }
          });
      });
    }
  }
});
