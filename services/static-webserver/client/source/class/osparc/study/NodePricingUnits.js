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

    this.set({
      studyId,
      nodeId,
    });
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

  properties: {
    studyId: {
      check: "String",
      init: null,
      nullable: false,
    },

    nodeId: {
      check: "String",
      init: null,
      nullable: false,
    },

    pricingPlanId: {
      check: "Number",
      init: null,
      nullable: false,
    },

    patchNode: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changePatchNode",
    },
  },

  statics: {
    patchPricingUnitSelection: function(studyId, nodeId, planId, selectedUnitId) {
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
    __nodeKey: null,
    __nodeVersion: null,
    __nodeLabel: null,
    __pricingUnits: null,

    showPricingUnits: function(inGroupBox = true) {
      return new Promise(resolve => {
        const nodeKey = this.__nodeKey;
        const nodeVersion = this.__nodeVersion;
        const nodeLabel = this.__nodeLabel;
        const studyId = this.getStudyId();
        const nodeId = this.getNodeId();

        osparc.store.Pricing.getInstance().fetchPricingPlansService(nodeKey, nodeVersion)
          .then(pricingPlanData => {
            if (pricingPlanData) {
              const unitParams = {
                url: {
                  studyId,
                  nodeId
                }
              };
              this.set({
                pricingPlanId: pricingPlanData["pricingPlanId"]
              });
              osparc.data.Resources.fetch("studies", "getPricingUnit", unitParams)
                .then(preselectedPricingUnit => {
                  if (pricingPlanData && "pricingUnits" in pricingPlanData && pricingPlanData["pricingUnits"].length) {
                    const pricingUnitsData = pricingPlanData["pricingUnits"];
                    const pricingUnitTiers = this.__pricingUnits = new osparc.study.PricingUnitTiers(pricingUnitsData, preselectedPricingUnit);
                    if (inGroupBox) {
                      const pricingUnitsLayout = osparc.study.StudyOptions.createGroupBox(nodeLabel);
                      pricingUnitsLayout.add(pricingUnitTiers);
                      this._add(pricingUnitsLayout);
                    } else {
                      this._add(pricingUnitTiers);
                    }
                    pricingUnitTiers.addListener("selectPricingUnitRequested", e => {
                      const selectedPricingUnitId = e.getData();
                      if (this.isPatchNode()) {
                        pricingUnitTiers.setEnabled(false);
                        const pricingPlanId = this.getPricingPlanId();
                        this.self().patchPricingUnitSelection(studyId, nodeId, pricingPlanId, selectedPricingUnitId)
                          .then(() => pricingUnitTiers.setSelectedUnitId(selectedPricingUnitId))
                          .catch(err => {
                            const msg = err.message || this.tr("Cannot change Tier");
                            osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
                          })
                          .finally(() => pricingUnitTiers.setEnabled(true));
                      }
                    });
                  }
                })
                .finally(() => resolve());
            }
          });
      });
    },

    getPricingUnits: function() {
      return this.__pricingUnits;
    },
  }
});
